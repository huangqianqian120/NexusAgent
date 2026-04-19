import { cn } from '../lib/utils';
import type { TranscriptItem } from '../types';
import { Bot, User, Terminal, AlertCircle, CheckCircle2 } from 'lucide-react';

interface MessageBubbleProps {
  item: TranscriptItem;
}

function formatTime(timestamp: number | undefined): string {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

export function MessageBubble({ item }: MessageBubbleProps) {
  const roleStyles = {
    user: 'bg-primary text-primary-foreground ml-auto',
    assistant: 'bg-muted',
    system: 'bg-destructive/10 text-destructive border border-destructive/20',
    tool: 'bg-orange-500/10 border border-orange-500/20',
    tool_result: 'bg-blue-500/10 border border-blue-500/20',
    log: 'bg-muted/50 text-muted-foreground italic',
  };

  const roleIcons = {
    user: <User className="w-4 h-4" />,
    assistant: <Bot className="w-4 h-4" />,
    system: <AlertCircle className="w-4 h-4" />,
    tool: <Terminal className="w-4 h-4" />,
    tool_result: <CheckCircle2 className="w-4 h-4" />,
    log: null,
  };

  const isUser = item.role === 'user';
  const isSystem = item.role === 'system';

  return (
    <div
      className={cn(
        'flex gap-3 max-w-[80%]',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      <div
        className={cn(
          'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
          isUser ? 'bg-primary' : 'bg-muted'
        )}
      >
        {roleIcons[item.role]}
      </div>
      <div
        className={cn(
          'rounded-lg px-4 py-2',
          roleStyles[item.role],
          isUser && 'rounded-tr-none',
          !isUser && !isSystem && 'rounded-tl-none'
        )}
      >
        {item.tool_name && (
          <div className="text-xs font-mono opacity-70 mb-1">
            {item.tool_name}
          </div>
        )}
        <div className="whitespace-pre-wrap break-words text-sm">
          {item.text}
        </div>
        {item.is_error && (
          <div className="text-xs text-destructive mt-1">Error</div>
        )}
        {item.timestamp && (
          <div className="text-xs opacity-50 mt-1">
            {formatTime(item.timestamp)}
          </div>
        )}
      </div>
    </div>
  );
}
