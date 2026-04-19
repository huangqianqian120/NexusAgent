import { useState, useEffect, useCallback } from 'react';
import {
  History,
  Trash2,
  RotateCcw,
  MessageSquare,
  Bot,
  Loader2,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { listSessions, deleteSession, type Session } from '../lib/api';

interface SessionPanelProps {
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  currentSessionId?: string;
}

export function SessionPanel({
  onSelectSession,
  onNewChat,
  currentSessionId,
}: SessionPanelProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listSessions();
      setSessions(data);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setDeletingId(sessionId);
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (error) {
      console.error('Failed to delete session:', error);
    } finally {
      setDeletingId(null);
    }
  };

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const day = 24 * 60 * 60 * 1000;

    if (diff < day && date.getDate() === now.getDate()) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    } else if (diff < 7 * day) {
      const days = Math.floor(diff / day);
      return `${days}天前`;
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-[hsl(240,3.7%,15.9%)]">
        <button
          onClick={onNewChat}
          className={cn(
            'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl',
            'bg-gradient-to-r from-[hsl(168,100%,50%)] to-[hsl(187,100%,50%)]',
            'text-[hsl(240,10%,3.9%)] font-medium text-sm',
            'hover:shadow-[0_0_20px_hsl(168,100%,50%)/0.4] transition-all duration-300',
            'btn-cyber'
          )}
        >
          <MessageSquare className="w-4 h-4" />
          新对话
        </button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto p-2">
        <div className="flex items-center gap-2 px-3 py-2">
          <History className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
          <span className="text-xs font-medium text-[hsl(240,5%,64.9%)] uppercase tracking-wider">
            历史会话
          </span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 text-[hsl(168,100%,50%)] animate-spin" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-8 text-[hsl(240,5%,64.9%)] text-sm">
            暂无历史会话
          </div>
        ) : (
          <div className="space-y-1">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  'w-full flex items-start gap-3 p-3 rounded-xl text-left transition-all duration-200',
                  'hover:bg-[hsl(240,3.7%,15.9%)] group',
                  currentSessionId === session.id && 'bg-[hsl(168,100%,50%)]/10 border border-[hsl(168,100%,50%)]/30'
                )}
              >
                <div className="w-8 h-8 rounded-lg bg-[hsl(240,3.7%,15.9%)] flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-[hsl(168,100%,50%)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[hsl(0,0%,98%)] truncate">
                    {session.summary || '(无内容)'}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-[hsl(240,5%,64.9%)]">
                      {session.message_count} 条消息
                    </span>
                    <span className="text-xs text-[hsl(240,5%,64.9%)]">·</span>
                    <span className="text-xs text-[hsl(240,5%,64.9%)]">
                      {formatTime(session.timestamp)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectSession(session.id);
                    }}
                    className="p-1.5 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)] text-[hsl(240,5%,64.9%)] hover:text-[hsl(168,100%,50%)]"
                    title="恢复会话"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={(e) => handleDelete(e, session.id)}
                    disabled={deletingId === session.id}
                    className="p-1.5 rounded-lg hover:bg-red-500/10 text-[hsl(240,5%,64.9%)] hover:text-red-400"
                    title="删除会话"
                  >
                    {deletingId === session.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
