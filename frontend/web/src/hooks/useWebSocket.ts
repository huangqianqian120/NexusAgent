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

// 创建 Socket.IO 连接并绑定事件处理器
function createSocket(
  url: string,
  handlers: {
    onConnect: (socket: Socket) => void;
    onEvent: (event: BackendEvent) => void;
  }
): Socket {
  const socket = io(url, {
    transports: ['polling', 'websocket'],
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
  });

  socket.on('connect', () => handlers.onConnect(socket));

  socket.on('disconnect', () => {
    // handled by shared state
  });

  socket.on('message', (data: unknown) => {
    let raw: string;
    if (typeof data === 'string') {
      raw = data;
    } else if (Array.isArray(data)) {
      raw = data[0];
    } else if (data && typeof data === 'object' && 'data' in data) {
      raw = typeof (data as Record<string, unknown>).data === 'string'
        ? (data as Record<string, string>).data
        : JSON.stringify((data as Record<string, unknown>).data);
    } else {
      raw = JSON.stringify(data);
    }
    if (!raw.startsWith(PROTOCOL_PREFIX)) {
      return;
    }
    try {
      const event: BackendEvent = JSON.parse(raw.slice(PROTOCOL_PREFIX.length));
      handlers.onEvent(event);
    } catch {
      // 忽略解析失败的消息
    }
  });

  return socket;
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
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const socketRef = useRef<Socket | null>(null);
  const assistantBufferRef = useRef<string>('');
  const inProgressIndexRef = useRef<number>(-1);

  const handleEvent = useCallback((event: BackendEvent) => {
    switch (event.type) {
      case 'ready':
        setStatus(event.state || null);
        setCommands(event.commands || []);
        setReady(true);
        setBusy(false);
        break;

      case 'state_snapshot':
        if (event.state) {
          setStatus(event.state);
        }
        break;

      case 'transcript_item':
        if (event.item) {
          setTranscript((prev) => [...prev, { ...event.item!, timestamp: Date.now() }]);
          assistantBufferRef.current = '';
          if (event.item!.role === 'user') {
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
            if (inProgressIndexRef.current >= 0 && inProgressIndexRef.current < newTranscript.length) {
              newTranscript[inProgressIndexRef.current] = {
                ...newTranscript[inProgressIndexRef.current],
                text: assistantBufferRef.current,
              };
            } else {
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
        setBusy(false);
        if (event.item) {
          setTranscript((prev) => {
            const newTranscript = [...prev];
            if (inProgressIndexRef.current >= 0 && inProgressIndexRef.current < newTranscript.length) {
              newTranscript[inProgressIndexRef.current] = event.item!;
            } else {
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
        setBusy(false);
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

      case 'clear_transcript':
        setTranscript([]);
        break;

      case 'plan_mode_change':
        if (event.plan_mode && status) {
          setStatus({ ...status, permission_mode: event.plan_mode });
        }
        break;
    }
  }, []);

  // 主连接初始化
  useEffect(() => {
    const socket = createSocket(url, {
      onConnect: () => {
        setReady(true);
        setReconnecting(false);
        socket.emit('session_start', {});
      },
      onEvent: handleEvent,
    });

    socket.on('disconnect', () => setReady(false));

    socket.on('reconnect_attempt', () => {
      setReconnecting(true);
    });

    socket.on('reconnect_failed', () => setReconnecting(false));

    socket.on('connect_error', () => {
      // 连接错误由 reconnect 机制处理
    });

    socket.on('error', () => {
      // Socket 级别错误
    });

    socketRef.current = socket;

    return () => {
      socket.disconnect();
    };
  }, [url, handleEvent]);

  const sendRequest = useCallback((request: FrontendRequest) => {
    if (socketRef.current?.connected) {
      if (request.type === 'submit_line') {
        setThinking(true);
        setBusy(true);
      }
      socketRef.current.emit('message', JSON.stringify(request));
    }
  }, []);

  const clearSelectRequest = useCallback(() => setSelectRequest(null), []);
  const clearPermissionRequest = useCallback(() => setPermissionRequest(null), []);
  const clearQuestionRequest = useCallback(() => setQuestionRequest(null), []);

  const resumeSession = useCallback((sessionId: string) => {
    // 断开当前连接
    if (socketRef.current?.connected) {
      socketRef.current.disconnect();
    }

    const newSocket = createSocket(url, {
      onConnect: () => {
        setReady(true);
        setReconnecting(false);
        setTranscript([]);
        setBusy(false);
        newSocket.emit('session_resume', { session_id: sessionId });
      },
      onEvent: handleEvent,
    });

    newSocket.on('disconnect', () => setReady(false));

    newSocket.on('reconnect_attempt', () => {
      setReconnecting(true);
    });

    newSocket.on('reconnect_failed', () => setReconnecting(false));

    newSocket.on('connect_error', () => {
      // 连接错误由 reconnect 机制处理
    });

    newSocket.on('error', () => {
      // Socket 级别错误
    });

    socketRef.current = newSocket;
  }, [url, handleEvent]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    setReady(false);
    setTranscript([]);
    setBusy(false);
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
