import { Moon, Sun, Plus, Minus, Loader2, Check } from 'lucide-react';
import { cn } from '../lib/utils';
import type { AppState, Theme } from '../types';
import type { Provider } from '../lib/api';

interface AppSettingsProps {
  status: AppState | null;
  commands: string[];
  profiles: Record<string, Provider>;
  switchingProfile: string | null;
  onCommandSelect: (command: string) => void;
  onSwitchProfile: (profileName: string) => void;
  onSend: (message: string) => void;
  onSetTheme: (theme: Theme) => void;
  onOpenModelSelector: () => void;
  currentTheme: string;
}

export function AppSettings({
  status,
  commands,
  profiles,
  switchingProfile,
  onCommandSelect,
  onSwitchProfile,
  onSend,
  onSetTheme,
  onOpenModelSelector,
  currentTheme,
}: AppSettingsProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        <h2 className="text-xl font-semibold text-[hsl(0,0%,98%)]">Settings</h2>

        {/* Provider & Model Card */}
        <div className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] p-6">
          <h3 className="text-sm font-medium text-[hsl(0,0%,98%)] mb-4">Provider & Model</h3>

          {/* Provider Profiles */}
          <div className="space-y-2 mb-4">
            <p className="text-xs text-[hsl(240,5%,64.9%)] uppercase tracking-wider">Provider Profiles</p>
            {Object.values(profiles).map((profile, index) => (
              <button
                key={profile.name || index}
                onClick={() => profile.name && onSwitchProfile(profile.name)}
                disabled={switchingProfile !== null}
                className={cn(
                  'w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-all',
                  profile.active
                    ? 'bg-[hsl(168,100%,50%)]/10 border border-[hsl(168,100%,50%)]/30'
                    : 'bg-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,25.9%)] border border-transparent'
                )}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[hsl(0,0%,98%)]">{profile.label || profile.name}</span>
                    {!profile.configured && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400">
                        Unconfigured
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-[hsl(240,5%,64.9%)]">{profile.provider}</span>
                    {profile.model && (
                      <>
                        <span className="text-xs text-[hsl(240,5%,64.9%)]">·</span>
                        <span className="text-xs text-[hsl(168,100%,50%)]">{profile.model}</span>
                      </>
                    )}
                  </div>
                </div>
                {switchingProfile === profile.name ? (
                  <Loader2 className="w-4 h-4 text-[hsl(168,100%,50%)] animate-spin" />
                ) : profile.active ? (
                  <div className="w-5 h-5 rounded-full bg-[hsl(168,100%,50%)] flex items-center justify-center">
                    <Check className="w-3 h-3 text-[hsl(240,10%,3.9%)]" />
                  </div>
                ) : null}
              </button>
            ))}
          </div>

          {/* Current Model */}
          <div className="flex items-center justify-between pt-4 border-t border-[hsl(240,3.7%,15.9%)]">
            <div>
              <p className="text-xs text-[hsl(240,5%,64.9%)]">当前模型</p>
              <button
                onClick={onOpenModelSelector}
                className="text-sm font-medium text-[hsl(168,100%,50%)] hover:underline"
              >
                {status?.model || 'N/A'}
              </button>
            </div>
            <button
              onClick={onOpenModelSelector}
              className="px-3 py-1.5 rounded-lg bg-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,25.9%)] text-xs text-[hsl(168,100%,50%)] transition-colors"
            >
              切换
            </button>
          </div>
        </div>

        {/* Commands Card */}
        <div className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] p-6">
          <h3 className="text-sm font-medium text-[hsl(0,0%,98%)] mb-4">常用命令</h3>
          <div className="grid grid-cols-2 gap-2">
            {commands.slice(0, 8).map((cmd) => (
              <button
                key={cmd}
                onClick={() => onCommandSelect(cmd.replace('/', ''))}
                className="px-3 py-2 rounded-lg bg-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,25.9%)] text-xs text-[hsl(240,5%,64.9%)] hover:text-[hsl(168,100%,50%)] transition-colors text-left font-mono"
              >
                {cmd}
              </button>
            ))}
          </div>
        </div>

        {/* Appearance Card */}
        <div className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] p-6">
          <h3 className="text-sm font-medium text-[hsl(0,0%,98%)] mb-4">Appearance</h3>
          <div className="flex gap-3">
            <button
              onClick={() => onSetTheme('dark')}
              className={cn(
                'flex-1 p-4 rounded-lg border transition-all',
                currentTheme === 'dark'
                  ? 'border-[hsl(168,100%,50%)] bg-[hsl(168,100%,50%)]/10'
                  : 'border-[hsl(240,3.7%,15.9%)] hover:border-[hsl(240,3.7%,25.9%)]'
              )}
            >
              <Moon className="w-5 h-5 mx-auto mb-2 text-[hsl(168,100%,50%)]" />
              <p className="text-xs font-medium text-center">Dark</p>
            </button>
            <button
              onClick={() => onSetTheme('light')}
              className={cn(
                'flex-1 p-4 rounded-lg border transition-all',
                currentTheme === 'light'
                  ? 'border-[hsl(168,100%,50%)] bg-[hsl(168,100%,50%)]/10'
                  : 'border-[hsl(240,3.7%,15.9%)] hover:border-[hsl(240,3.7%,25.9%)]'
              )}
            >
              <Sun className="w-5 h-5 mx-auto mb-2 text-[hsl(168,100%,50%)]" />
              <p className="text-xs font-medium text-center">Light</p>
            </button>
          </div>
        </div>

        {/* Vim Mode Card */}
        <div className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-[hsl(0,0%,98%)]">Vim Mode</h3>
              <p className="text-xs text-[hsl(240,5%,64.9%)] mt-1">使用 Vim 键盘快捷键操作输入框</p>
            </div>
            <button
              onClick={() => onSend('/toggle-vim')}
              className={cn(
                'relative w-12 h-6 rounded-full transition-colors',
                status?.vim_enabled
                  ? 'bg-[hsl(168,100%,50%)]'
                  : 'bg-[hsl(240,3.7%,25.9%)]'
              )}
            >
              <span
                className={cn(
                  'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                  status?.vim_enabled ? 'left-7' : 'left-1'
                )}
              />
            </button>
          </div>
        </div>

        {/* Fast Mode Card */}
        <div className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-[hsl(0,0%,98%)]">Fast Mode</h3>
              <p className="text-xs text-[hsl(240,5%,64.9%)] mt-1">跳过确认步骤，加速执行流程</p>
            </div>
            <button
              onClick={() => onSend('/toggle-fast')}
              className={cn(
                'relative w-12 h-6 rounded-full transition-colors',
                status?.fast_mode
                  ? 'bg-[hsl(168,100%,50%)]'
                  : 'bg-[hsl(240,3.7%,25.9%)]'
              )}
            >
              <span
                className={cn(
                  'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                  status?.fast_mode ? 'left-7' : 'left-1'
                )}
              />
            </button>
          </div>
        </div>

        {/* Voice Mode Card */}
        <div className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-[hsl(0,0%,98%)]">Voice Mode</h3>
              <p className="text-xs text-[hsl(240,5%,64.9%)] mt-1">
                {status?.voice_available === false
                  ? status?.voice_reason || '语音模式不可用'
                  : '启用语音输入和播报'}
              </p>
            </div>
            <button
              onClick={() => onSend('/toggle-voice')}
              disabled={status?.voice_available === false}
              className={cn(
                'relative w-12 h-6 rounded-full transition-colors',
                status?.voice_enabled
                  ? 'bg-[hsl(168,100%,50%)]'
                  : 'bg-[hsl(240,3.7%,25.9%)]',
                status?.voice_available === false && 'opacity-50 cursor-not-allowed'
              )}
            >
              <span
                className={cn(
                  'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                  status?.voice_enabled ? 'left-7' : 'left-1'
                )}
              />
            </button>
          </div>
        </div>

        {/* Effort Level Card */}
        <div className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] p-6">
          <h3 className="text-sm font-medium text-[hsl(0,0%,98%)] mb-4">Effort Level</h3>
          <div className="grid grid-cols-3 gap-2">
            {['low', 'medium', 'high'].map((level) => (
              <button
                key={level}
                onClick={() => onSend(`/set-effort ${level}`)}
                className={cn(
                  'px-3 py-2 rounded-lg text-xs font-medium transition-all',
                  status?.effort === level
                    ? 'bg-[hsl(168,100%,50%)] text-black'
                    : 'bg-[hsl(240,3.7%,15.9%)] text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,25.9%)]'
                )}
              >
                {level === 'low' ? '低' : level === 'medium' ? '中' : '高'}
              </button>
            ))}
          </div>
          <p className="text-xs text-[hsl(240,5%,64.9%)] mt-3">
            {status?.effort === 'low' ? '快速响应，最小化反思' :
             status?.effort === 'high' ? '深度分析，更多迭代' :
             '平衡速度与质量'}
          </p>
        </div>

        {/* Passes Card */}
        <div className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] p-6">
          <h3 className="text-sm font-medium text-[hsl(0,0%,98%)] mb-4">Passes</h3>
          <div className="flex items-center gap-4">
            <button
              onClick={() => onSend('/set-passes -1')}
              className="w-8 h-8 rounded-lg bg-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,25.9%)] text-[hsl(0,0%,98%)] transition-colors flex items-center justify-center"
            >
              <Minus className="w-4 h-4" />
            </button>
            <div className="flex-1 text-center">
              <span className="text-2xl font-bold text-[hsl(168,100%,50%)]">{status?.passes ?? 0}</span>
              <p className="text-xs text-[hsl(240,5%,64.9%)] mt-1">次迭代</p>
            </div>
            <button
              onClick={() => onSend('/set-passes 1')}
              className="w-8 h-8 rounded-lg bg-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,25.9%)] text-[hsl(0,0%,98%)] transition-colors flex items-center justify-center"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
          <p className="text-xs text-[hsl(240,5%,64.9%)] mt-3">增加迭代次数可获得更详细的结果</p>
        </div>

        {/* Permission Mode Card */}
        <div className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] p-6">
          <h3 className="text-sm font-medium text-[hsl(0,0%,98%)] mb-4">Permission Mode</h3>
          <div className="grid grid-cols-2 gap-2">
            {[
              { value: 'allow', label: '允许' },
              { value: 'warn', label: '警告' },
              { value: 'deny', label: '拒绝' },
              { value: 'bypass', label: '绕过' },
            ].map((mode) => (
              <button
                key={mode.value}
                onClick={() => onSend(`/set-permission ${mode.value}`)}
                className={cn(
                  'px-3 py-2 rounded-lg text-xs font-medium transition-all',
                  status?.permission_mode === mode.value
                    ? 'bg-[hsl(168,100%,50%)] text-black'
                    : 'bg-[hsl(240,3.7%,15.9%)] text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,25.9%)]'
                )}
              >
                {mode.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-[hsl(240,5%,64.9%)] mt-3">
            控制工具执行的权限级别
          </p>
        </div>
      </div>
    </div>
  );
}
