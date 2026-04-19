import { Moon, Sun, Wifi, WifiOff, Bot } from 'lucide-react';
import { cn } from '../lib/utils';
import type { AppState } from '../types';

interface StatusBarProps {
  status: AppState | null;
  connected: boolean;
  onThemeToggle: () => void;
  theme: 'light' | 'dark' | 'system';
}

export function StatusBar({ status, connected, onThemeToggle, theme }: StatusBarProps) {
  const themeIcon = theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />;

  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center justify-between px-4 py-2">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-primary" />
            <span className="font-semibold">NexusAgent</span>
          </div>
          {status && (
            <div className="hidden md:flex items-center gap-4 text-sm text-muted-foreground">
              <span>
                <span className="font-medium text-foreground">{status.model}</span>
              </span>
              <span className="text-muted">|</span>
              <span>{status.provider}</span>
              <span className="text-muted">|</span>
              <span>{status.permission_mode}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'flex items-center gap-1 text-xs px-2 py-1 rounded-full',
              connected
                ? 'bg-green-500/10 text-green-600'
                : 'bg-red-500/10 text-red-600'
            )}
          >
            {connected ? (
              <>
                <Wifi className="w-3 h-3" />
                Connected
              </>
            ) : (
              <>
                <WifiOff className="w-3 h-3" />
                Disconnected
              </>
            )}
          </div>
          <button
            onClick={onThemeToggle}
            className={cn(
              'p-2 rounded-lg hover:bg-muted transition-colors',
              'flex items-center justify-center'
            )}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {themeIcon}
          </button>
        </div>
      </div>
    </header>
  );
}
