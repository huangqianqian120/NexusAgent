import { Loader2, Wifi, WifiOff, Zap, ChevronDown, Moon, Sun } from 'lucide-react';
import { cn } from '../lib/utils';
import type { Status, Theme } from '../types';

interface AppHeaderProps {
  status: Status | null;
  ready: boolean;
  reconnecting: boolean;
  theme: Theme;
  toggleTheme: () => void;
  onOpenModelSelector: () => void;
}

export function AppHeader({
  status,
  ready,
  reconnecting,
  theme,
  toggleTheme,
  onOpenModelSelector,
}: AppHeaderProps) {
  return (
    <header className="h-14 border-b border-[hsl(240,3.7%,15.9%)] flex items-center justify-between px-4 bg-[hsl(240,10%,3.9%)]/80 backdrop-blur">
      <div className="flex items-center gap-3">
        <span className="font-semibold text-lg cyber-glow-text text-[hsl(168,100%,50%)]">
          NexusAgent
        </span>
      </div>

      <div className="flex items-center gap-4">
        {/* Connection Status */}
        <div
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
            reconnecting
              ? 'bg-[hsl(45,93%,47%)]/10 text-[hsl(45,93%,47%)] border border-[hsl(45,93%,47%)]/30'
              : ready
              ? 'bg-[hsl(142,76%,45%)]/10 text-[hsl(142,76%,45%)] border border-[hsl(142,76%,45%)]/30'
              : 'bg-[hsl(0,84%,60%)]/10 text-[hsl(0,84%,60%)] border border-[hsl(0,84%,60%)]/30'
          )}
        >
          {reconnecting ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Reconnecting...</span>
            </>
          ) : ready ? (
            <>
              <Wifi className="w-3 h-3" />
              <span>Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3 h-3" />
              <span>Disconnected</span>
            </>
          )}
        </div>

        {/* Model Badge */}
        <button
          onClick={onOpenModelSelector}
          className={cn(
            'hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full',
            'bg-[hsl(240,3.7%,15.9%)] border border-[hsl(240,3.7%,15.9%)]',
            'hover:border-[hsl(168,100%,50%)]/50 transition-colors cursor-pointer'
          )}
        >
          <Zap className="w-3 h-3 text-[hsl(168,100%,50%)]" />
          <span className="text-xs font-medium">{status?.model || 'Select Model'}</span>
          <ChevronDown className="w-3 h-3 text-[hsl(240,5%,64.9%)]" />
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-[hsl(168,100%,50%)]" />
          ) : (
            <Moon className="w-4 h-4 text-[hsl(168,100%,50%)]" />
          )}
        </button>
      </div>
    </header>
  );
}
