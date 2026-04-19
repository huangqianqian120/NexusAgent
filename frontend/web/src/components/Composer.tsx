import { useState, useRef, useEffect } from 'react';
import { Send, Square, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { CommandPalette } from './CommandPalette';

interface ComposerProps {
  onSend: (message: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
  busy?: boolean;
  commands?: string[];
}

export function Composer({ onSend, onCancel, disabled, busy, commands = [] }: ComposerProps) {
  const [message, setMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showCommands, setShowCommands] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [message]);

  const handleSubmit = (e: React.FormEvent) => {
    // This is only called by button click now
    e.preventDefault();
    console.log('[Composer] handleSubmit called via button, message:', message, 'disabled:', disabled, 'busy:', busy, 'isSubmitting:', isSubmitting);
    if (!message.trim() || disabled || busy || isSubmitting) {
      console.log('[Composer] Submit blocked:', !message.trim() ? 'empty' : disabled ? 'disabled' : busy ? 'busy' : 'submitting');
      return;
    }
    console.log('[Composer] Sending message:', message.trim());
    setIsSubmitting(true);
    onSend(message.trim());
    setMessage('');
    setTimeout(() => setIsSubmitting(false), 100);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Show command palette when user types /
    if (e.key === '/' && !showCommands && message === '') {
      setShowCommands(true);
      return;
    }

    if (showCommands) {
      if (e.key === 'Escape') {
        e.preventDefault();
        setShowCommands(false);
      }
      return;
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      // Use setTimeout to avoid React state update batch issues
      setTimeout(() => {
        if (message.trim() && !disabled && !busy && !isSubmitting) {
          setIsSubmitting(true);
          onSend(message.trim());
          setMessage('');
          setTimeout(() => setIsSubmitting(false), 100);
        }
      }, 0);
    }
    if (e.key === 'Escape' && busy && onCancel) {
      e.preventDefault();
      onCancel();
    }
  };

  const handleCommandSelect = (cmd: string) => {
    setMessage(`/${cmd} `);
    setShowCommands(false);
    textareaRef.current?.focus();
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      {/* Input Container */}
      <div className="relative rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] transition-all hover:border-[hsl(168,100%,50%)]/30 focus-within:border-[hsl(168,100%,50%)]/50 focus-within:shadow-[0_0_20px_hsl(168,100%,50%)]/0.1]">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={busy ? 'Waiting for response...' : 'Type a message...'}
          disabled={disabled || busy}
          className={cn(
            'w-full resize-none rounded-lg bg-transparent px-4 py-3 pr-24 text-sm',
            'focus:outline-none focus:ring-0',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'min-h-[52px] max-h-[200px]',
            'placeholder:text-[hsl(240,5%,64.9%)]'
          )}
          rows={1}
        />

        {/* Action Buttons */}
        <div className="absolute right-2 bottom-2 flex items-center gap-2">
          {busy ? (
            <button
              type="button"
              onClick={onCancel}
              className={cn(
                'h-9 px-3 rounded-lg flex items-center justify-center gap-2',
                'bg-red-500/10 text-red-400 border border-red-500/30',
                'hover:bg-red-500/20 transition-all'
              )}
            >
              <Square className="w-4 h-4" />
              <span className="text-xs font-medium">Stop</span>
            </button>
          ) : (
            <button
              type="submit"
              disabled={!message.trim() || disabled}
              className={cn(
                'h-9 px-4 rounded-lg flex items-center justify-center gap-2',
                'bg-gradient-to-r from-[hsl(168,100%,50%)] to-[hsl(187,100%,50%)]',
                'text-[hsl(240,10%,3.9%)] font-medium',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'hover:shadow-[0_0_20px_hsl(168,100%,50%)/0.4] transition-all duration-300',
                'btn-cyber'
              )}
            >
              <Send className="w-4 h-4" />
              <span className="text-sm">Send</span>
            </button>
          )}
        </div>
      </div>

      {/* Command Palette */}
      {showCommands && (
        <CommandPalette
          commands={commands.map((cmd) => ({
            name: cmd,
            description: '',
          }))}
          onSelect={handleCommandSelect}
          onClose={() => setShowCommands(false)}
        />
      )}

      {/* Hint */}
      <div className="flex items-center justify-between mt-2 px-1">
        <p className="text-[10px] text-[hsl(240,5%,64.9%)]">
          <kbd className="px-1.5 py-0.5 rounded bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]">/</kbd> 命令
          <span className="mx-2">·</span>
          <kbd className="px-1.5 py-0.5 rounded bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]">Enter</kbd> 发送
          <span className="mx-2">·</span>
          <kbd className="px-1.5 py-0.5 rounded bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]">Shift+Enter</kbd> 换行
        </p>
        {busy && (
          <div className="flex items-center gap-2 text-[hsl(168,100%,50%)]">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span className="text-xs">Processing...</span>
          </div>
        )}
      </div>
    </form>
  );
}
