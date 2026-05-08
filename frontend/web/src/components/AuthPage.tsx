import { useState, useEffect } from 'react';
import { login, register, getStoredUser, getMe, type UserInfo } from '../lib/auth';

interface Props {
  onLoginSuccess: (user: UserInfo) => void;
}

type Mode = 'login' | 'register';

export function AuthPage({ onLoginSuccess }: Props) {
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // 尝试自动登录（带缓存验证）
  useEffect(() => {
    const cached = getStoredUser();
    if (cached) {
      getMe()
        .then(user => onLoginSuccess(user))
        .catch(() => {});
    }
  }, [onLoginSuccess]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let user: UserInfo;
      if (mode === 'login') {
        const res = await login(email, password);
        user = res.user;
      } else {
        const res = await register(email, password, username);
        user = res.user;
      }
      onLoginSuccess(user);
    } catch (err: any) {
      setError(err.message || '操作失败，请重试');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center gradient-cyber relative overflow-hidden">
      {/* 背景网格 */}
      <div className="absolute inset-0 grid-cyber opacity-40" />

      {/* 背景光效 */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <div className="w-[500px] h-[500px] rounded-full bg-[hsl(var(--cyber-green))]/5 blur-[120px]" />
      </div>

      <div className="relative w-full max-w-md mx-4 px-4">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl cyber-border mb-5 cyber-glow">
            <svg className="w-8 h-8 text-[hsl(var(--cyber-green))]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-[hsl(var(--foreground))] cyber-glow-text">
            NexusAgent
          </h1>
          <p className="text-[hsl(var(--muted-foreground))] mt-2">
            多用户 AI 助手平台
          </p>
        </div>

        {/* 表单卡片 */}
        <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-2xl p-8 cyber-border">
          {/* Tab 切换 */}
          <div className="flex rounded-lg bg-[hsl(var(--muted))] p-1 mb-8">
            <button
              type="button"
              onClick={() => { setMode('login'); setError(''); }}
              className={`flex-1 py-2.5 text-sm font-medium rounded-md transition-all duration-200 ${
                mode === 'login'
                  ? 'bg-[hsl(var(--background))] text-[hsl(var(--foreground))] shadow-sm'
                  : 'text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
              }`}
            >
              登录
            </button>
            <button
              type="button"
              onClick={() => { setMode('register'); setError(''); }}
              className={`flex-1 py-2.5 text-sm font-medium rounded-md transition-all duration-200 ${
                mode === 'register'
                  ? 'bg-[hsl(var(--background))] text-[hsl(var(--foreground))] shadow-sm'
                  : 'text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
              }`}
            >
              注册
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* 用户名（仅注册显示） */}
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-medium text-[hsl(var(--muted-foreground))] mb-2">
                  用户名
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="输入用户名（选填）"
                  className="w-full px-4 py-3 rounded-lg bg-[hsl(var(--background))] border border-[hsl(var(--border))] text-[hsl(var(--foreground))] placeholder-[hsl(var(--muted-foreground))] transition-all"
                />
              </div>
            )}

            {/* 邮箱 */}
            <div>
              <label className="block text-sm font-medium text-[hsl(var(--muted-foreground))] mb-2">
                邮箱
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
                className="w-full px-4 py-3 rounded-lg bg-[hsl(var(--background))] border border-[hsl(var(--border))] text-[hsl(var(--foreground))] placeholder-[hsl(var(--muted-foreground))] transition-all"
              />
            </div>

            {/* 密码 */}
            <div>
              <label className="block text-sm font-medium text-[hsl(var(--muted-foreground))] mb-2">
                密码
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
                className="w-full px-4 py-3 rounded-lg bg-[hsl(var(--background))] border border-[hsl(var(--border))] text-[hsl(var(--foreground))] placeholder-[hsl(var(--muted-foreground))] transition-all"
              />
            </div>

            {/* 错误提示 */}
            {error && (
              <div className="px-4 py-3 rounded-lg bg-[hsl(var(--error))]/10 border border-[hsl(var(--error))]/20 text-[hsl(var(--error))] text-sm">
                {error}
              </div>
            )}

            {/* 提交按钮 */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-lg bg-[hsl(var(--cyber-green))] text-[hsl(var(--background))] font-medium hover:opacity-90 disabled:opacity-50 transition-all btn-cyber border border-[hsl(var(--cyber-green))] mt-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  处理中...
                </span>
              ) : mode === 'login' ? '登录' : '注册'}
            </button>
          </form>
        </div>

        {/* 底部说明 */}
        <p className="text-center text-[hsl(var(--muted-foreground))] text-xs mt-6">
          使用即表示同意服务条款
        </p>
      </div>
    </div>
  );
}
