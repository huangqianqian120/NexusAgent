import { Loader2, Wifi, WifiOff, Moon, Sun, Coins, LogOut } from 'lucide-react';
import { cn } from '../lib/utils';
import type { Theme } from '../types';
import type { UserInfo } from '../lib/auth';

interface AppHeaderProps {
  ready: boolean;
  reconnecting: boolean;
  theme: Theme;
  toggleTheme: () => void;
  currentUser?: UserInfo | null;
  onLogout: () => void;
}

export function AppHeader({
  ready,
  reconnecting,
  theme,
  toggleTheme,
  currentUser,
  onLogout,
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

        {/* Credits Badge */}
        {currentUser && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[hsl(45,93%,47%)]/10 border border-[hsl(45,93%,47%)]/30">
            <Coins className="w-3 h-3 text-[hsl(45,93%,47%)]" />
            <span className="text-xs font-medium text-[hsl(45,93%,47%)]">
              {parseFloat(currentUser.credits_balance).toFixed(2)} Credits
            </span>
          </div>
        )}

        {/* User Info & Logout */}
        {currentUser && (
          <div className="flex items-center gap-2">
            <div className="hidden sm:block text-right">
              <div className="text-xs font-medium text-[hsl(0,0%,98%)]">{currentUser.username}</div>
              <div className="text-xs text-[hsl(240,5%,64.9%)]">{currentUser.email}</div>
            </div>
            <button
              onClick={onLogout}
              title="退出登录"
              className="p-2 rounded-lg hover:bg-[hsl(0,84%,60%)]/10 text-[hsl(240,5%,64.9%)] hover:text-[hsl(0,84%,60%)] transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
