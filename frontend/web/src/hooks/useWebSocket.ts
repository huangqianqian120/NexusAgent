import { useEffect, useRef, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import type {
  BackendEvent,
  FrontendRequest,
  TranscriptItem,
  AppState,
  SelectRequest,
  PermissionRequest,
  QuestionRequest,
} from '../types';

const PROTOCOL_PREFIX = 'OHJSON:';

// 格式化错误消息为用户友好的文本
function formatUserError(message: string): string {
  const lower = message.toLowerCase();

  // 认证错误
  if (lower.includes('auth') || lower.includes('login') || lower.includes('token')) {
    if (lower.includes('expired') || lower.includes('invalid')) {
      return '登录已过期，请重新登录';
    }
    return '认证失败，请检查设置中的 API Key';
  }

  // 连接错误
  if (lower.includes('connect') || lower.includes('network') || lower.includes('timeout')) {
    return '网络连接失败，请检查网络后重试';
  }

  // 速率限制
  if (lower.includes('rate') || lower.includes('quota') || lower.includes('limit')) {
    return '请求过于频繁，请稍后再试';
  }

  // 默认返回原始消息
  return message;
}

interface UseWebSocketReturn {
  transcript: TranscriptItem[];
  status: AppState | null;
  ready: boolean;
  reconnecting: boolean;
  selectRequest: SelectRequest | null;
  permissionRequest: PermissionRequest | null;
  questionRequest: QuestionRequest | null;
  commands: string[];
  busy: boolean;
  thinking: boolean;
  sendRequest: (request: FrontendRequest) => void;
  clearSelectRequest: () => void;
  clearPermissionRequest: () => void;
  clearQuestionRequest: () => void;
  resumeSession: (sessionId: string) => void;
  disconnect: () => void;
}

export function useWebSocket(url: string): UseWebSocketReturn {
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [status, setStatus] = useState<AppState | null>(null);
  const [ready, setReady] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [selectRequest, setSelectRequest] = useState<SelectRequest | null>(null);
  const [permissionRequest, setPermissionRequest] = useState<PermissionRequest | null>(null);
  const [questionRequest, setQuestionRequest] = useState<QuestionRequest | null>(null);
  const [commands, setCommands] = useState<string[]>([]);
  const [busy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const socketRef = useRef<Socket | null>(null);
  const assistantBufferRef = useRef<string>('');
  const inProgressIndexRef = useRef<number>(-1);
  const lastUserMessageRef = useRef<number>(0);
  const reconnectAttemptRef = useRef<number>(0);

  const sendRequest = useCallback((request: FrontendRequest) => {
    if (socketRef.current?.connected) {
      // Set thinking state when user sends a message
      if (request.type === 'submit_line') {
        setThinking(true);
        lastUserMessageRef.current = Date.now();
      }
      socketRef.current.emit('message', JSON.stringify(request));
    }
  }, []);

  const clearSelectRequest = useCallback(() => setSelectRequest(null), []);
  const clearPermissionRequest = useCallback(() => setPermissionRequest(null), []);
  const clearQuestionRequest = useCallback(() => setQuestionRequest(null), []);

  useEffect(() => {
    const socket = io(url, {
      transports: ['polling', 'websocket'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('WebSocket connected');
      setReady(true);
      setReconnecting(false);
      reconnectAttemptRef.current = 0;
      socket.emit('session_start', {});
    });

    socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setReady(false);
    });

    socket.on('reconnect_attempt', () => {
      console.log('WebSocket reconnecting...', reconnectAttemptRef.current + 1);
      setReconnecting(true);
      reconnectAttemptRef.current += 1;
    });

    socket.on('reconnect_failed', () => {
      console.error('WebSocket reconnection failed');
      setReconnecting(false);
    });

    socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
    });

    socket.on('message', (data: any) => {
      console.log('Raw message received:', typeof data, data);
      // Socket.IO 5.x may send data in different formats
      let raw: string;
      if (typeof data === 'string') {
        raw = data;
      } else if (Array.isArray(data)) {
        raw = data[0];
      } else if (data?.data) {
        raw = typeof data.data === 'string' ? data.data : JSON.stringify(data.data);
      } else {
        raw = JSON.stringify(data);
      }
      if (!raw.startsWith(PROTOCOL_PREFIX)) {
        console.log('Ignoring non-protocol message');
        return;
      }
      try {
        const event: BackendEvent = JSON.parse(raw.slice(PROTOCOL_PREFIX.length));
        handleEvent(event);
      } catch (e) {
        console.error('Failed to parse event:', e);
      }
    });

    socket.on('error', (error: Error) => {
      console.error('WebSocket error:', error);
    });

    return () => {
      socket.disconnect();
    };
  }, [url]);

  const handleEvent = (event: BackendEvent) => {
    switch (event.type) {
      case 'ready':
        setStatus(event.state || null);
        setCommands(event.commands || []);
        if (event.tasks) {
          // Handle tasks snapshot
        }
        setReady(true);
        break;

      case 'state_snapshot':
        if (event.state) {
          setStatus(event.state);
        }
        if (event.mcp_servers) {
          // Handle MCP servers
        }
        break;

      case 'tasks_snapshot':
        // Handle tasks
        break;

      case 'transcript_item':
        if (event.item) {
          setTranscript((prev) => [...prev, { ...event.item!, timestamp: Date.now() }]);
          assistantBufferRef.current = '';
          // Reset in-progress tracking when user sends a new message
          if (event.item.role === 'user') {
            inProgressIndexRef.current = -1;
          }
        }
        break;

      case 'assistant_delta':
        setThinking(false);
        if (event.message) {
          assistantBufferRef.current += event.message;
          setTranscript((prev) => {
            const newTranscript = [...prev];
            // Use in-progress index to track current assistant message
            if (inProgressIndexRef.current >= 0 && inProgressIndexRef.current < newTranscript.length) {
              newTranscript[inProgressIndexRef.current] = {
                ...newTranscript[inProgressIndexRef.current],
                text: assistantBufferRef.current,
              };
            } else {
              // First delta for this message - create new assistant entry and track it
              const newIndex = newTranscript.length;
              newTranscript.push({
                role: 'assistant',
                text: assistantBufferRef.current,
                timestamp: Date.now(),
              });
              inProgressIndexRef.current = newIndex;
            }
            return newTranscript;
          });
        }
        break;

      case 'assistant_complete':
        if (event.item) {
          setTranscript((prev) => {
            const newTranscript = [...prev];
            // Use in-progress index to update the correct assistant message
            if (inProgressIndexRef.current >= 0 && inProgressIndexRef.current < newTranscript.length) {
              newTranscript[inProgressIndexRef.current] = event.item!;
            } else {
              // Fallback: find last assistant or push new
              const lastIndex = newTranscript.findLastIndex(
                (item: TranscriptItem) => item.role === 'assistant'
              );
              if (lastIndex >= 0) {
                newTranscript[lastIndex] = event.item!;
              } else {
                newTranscript.push(event.item!);
              }
            }
            return newTranscript;
          });
        }
        assistantBufferRef.current = '';
        inProgressIndexRef.current = -1;
        break;

      case 'tool_started':
        setThinking(false);
        if (event.item) {
          setTranscript((prev) => [...prev, event.item!]);
        }
        break;

      case 'tool_completed':
        // Update tool result
        break;

      case 'select_request':
        if (event.modal && event.select_options) {
          setSelectRequest({
            title: String(event.modal.title || 'Select'),
            command: String(event.modal.command || ''),
            options: event.select_options,
          });
        }
        break;

      case 'modal_request':
        if (event.modal) {
          if (event.modal.kind === 'permission') {
            setPermissionRequest({
              request_id: event.modal.request_id || '',
              tool_name: event.modal.tool_name || '',
              reason: event.modal.reason || '',
            });
          } else if (event.modal.kind === 'question') {
            setQuestionRequest({
              request_id: event.modal.request_id || '',
              question: event.modal.question || '',
            });
          }
        }
        break;

      case 'error':
        setThinking(false);
        if (event.message) {
          const friendlyMessage = formatUserError(event.message);
          setTranscript((prev) => [
            ...prev,
            {
              role: 'system',
              text: friendlyMessage !== event.message ? `${friendlyMessage}\n(${event.message})` : friendlyMessage,
              is_error: true,
              timestamp: Date.now(),
            },
          ]);
        }
        break;

      case 'shutdown':
        // Don't set ready=false on shutdown - let user continue
        // The session may still be usable after a brief shutdown
        console.log('Received shutdown event, keeping ready=true');
        break;

      case 'clear_transcript':
        setTranscript([]);
        break;

      case 'plan_mode_change':
        if (event.plan_mode && status) {
          setStatus({ ...status, permission_mode: event.plan_mode });
        }
        break;
    }
  };

  const resumeSession = useCallback((sessionId: string) => {
    if (socketRef.current?.connected) {
      // Disconnect current session first
      socketRef.current.disconnect();
    }

    // Create new socket for the session
    const newSocket = io(url, {
      transports: ['polling', 'websocket'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    socketRef.current = newSocket;

    newSocket.on('connect', () => {
      console.log('WebSocket connected for session resume:', sessionId);
      setReady(true);
      setReconnecting(false);
      setTranscript([]); // Clear transcript for new session
      newSocket.emit('session_resume', { session_id: sessionId });
    });

    newSocket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setReady(false);
    });

    newSocket.on('reconnect_attempt', () => {
      console.log('WebSocket reconnecting...');
      setReconnecting(true);
    });

    newSocket.on('reconnect_failed', () => {
      console.error('WebSocket reconnection failed');
      setReconnecting(false);
    });

    newSocket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
    });

    newSocket.on('message', (data: any) => {
      console.log('Raw message received:', typeof data, data);
      let raw: string;
      if (typeof data === 'string') {
        raw = data;
      } else if (Array.isArray(data)) {
        raw = data[0];
      } else if (data?.data) {
        raw = typeof data.data === 'string' ? data.data : JSON.stringify(data.data);
      } else {
        raw = JSON.stringify(data);
      }
      if (!raw.startsWith(PROTOCOL_PREFIX)) {
        console.log('Ignoring non-protocol message');
        return;
      }
      try {
        const event: BackendEvent = JSON.parse(raw.slice(PROTOCOL_PREFIX.length));
        handleEvent(event);
      } catch (e) {
        console.error('Failed to parse event:', e);
      }
    });

    newSocket.on('error', (error: Error) => {
      console.error('WebSocket error:', error);
    });
  }, [url]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    setReady(false);
    setTranscript([]);
  }, []);

  return {
    transcript,
    status,
    ready,
    reconnecting,
    selectRequest,
    permissionRequest,
    questionRequest,
    commands,
    busy,
    thinking,
    sendRequest,
    clearSelectRequest,
    clearPermissionRequest,
    clearQuestionRequest,
    resumeSession,
    disconnect,
  };
}
