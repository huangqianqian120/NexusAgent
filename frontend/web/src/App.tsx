import { useCallback, useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useTheme } from './hooks/useTheme';
import { Composer } from './components/Composer';
import { ChatView } from './components/ChatView';
import { SelectModal } from './components/SelectModal';
import { PermissionDialog } from './components/PermissionDialog';
import { SessionPanel } from './components/SessionPanel';
import { ModelSelector } from './components/ModelSelector';
import { SkillsPanel } from './components/SkillsPanel';
import { AgentPlayground } from './components/AgentPlayground';
import { TasksPanel } from './components/TasksPanel';
import { MemoryPanel } from './components/MemoryPanel';
import {
  MessageSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Moon,
  Sun,
  Zap,
  Wifi,
  WifiOff,
  History,
  Trash2,
  Plus,
  Minus,
  Loader2,
  Code,
  Wrench,
  Bot,
  Check,
  Brain,
} from 'lucide-react';
import { cn } from './lib/utils';
import { getAllProfiles, switchProvider, type Provider } from './lib/api';

const WS_URL = `${window.location.protocol}//${window.location.hostname}:8765`;

export function App() {
  const [theme, setTheme, toggleTheme] = useTheme();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<'chat' | 'settings' | 'playground'>('chat');
  const [showSessionPanel, setShowSessionPanel] = useState(false);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [showSkillsPanel, setShowSkillsPanel] = useState(false);
  const [showTasksPanel, setShowTasksPanel] = useState(false);
  const [showMemoryPanel, setShowMemoryPanel] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>();
  const [profiles, setProfiles] = useState<Record<string, Provider>>({});
  const [switchingProfile, setSwitchingProfile] = useState<string | null>(null);

  // Fetch profiles when switching to settings tab
  useEffect(() => {
    if (activeTab === 'settings') {
      getAllProfiles().then(setProfiles).catch(console.error);
    }
  }, [activeTab]);

  const {
    transcript,
    status,
    ready,
    reconnecting,
    selectRequest,
    permissionRequest,
    commands,
    busy,
    thinking,
    sendRequest,
    clearSelectRequest,
    clearPermissionRequest,
    resumeSession,
  } = useWebSocket(WS_URL);

  const handleSend = useCallback(
    (message: string) => {
      sendRequest({ type: 'submit_line', line: message });
    },
    [sendRequest]
  );

  const handleSelect = useCallback(
    (command: string, value: string) => {
      sendRequest({ type: 'apply_select_command', command, value });
      clearSelectRequest();
    },
    [sendRequest, clearSelectRequest]
  );

  const handlePermission = useCallback(
    (allowed: boolean, requestId: string) => {
      sendRequest({ type: 'permission_response', allowed, request_id: requestId });
      clearPermissionRequest();
    },
    [sendRequest, clearPermissionRequest]
  );

  const handleCommandSelect = useCallback(
    (command: string) => {
      sendRequest({ type: 'select_command', command });
    },
    [sendRequest]
  );

  const handleSwitchProfile = useCallback(async (profileName: string) => {
    setSwitchingProfile(profileName);
    try {
      await switchProvider(profileName);
      // Refresh profiles to update active state
      const newProfiles = await getAllProfiles();
      setProfiles(newProfiles);
    } catch (error) {
      console.error('Failed to switch profile:', error);
    } finally {
      setSwitchingProfile(null);
    }
  }, []);

  const handleNewChat = useCallback(() => {
    // Clear current transcript and start fresh by sending /clear command
    sendRequest({ type: 'submit_line', line: '/clear' });
    setCurrentSessionId(undefined);
    setShowSessionPanel(false);
  }, [sendRequest]);

  const handleSelectSession = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
    setShowSessionPanel(false);
    console.log('Session resume requested:', sessionId);
    // Resume the session via WebSocket
    resumeSession(sessionId);
  }, [resumeSession]);

  const handleClearSession = useCallback(() => {
    handleCommandSelect('clear');
  }, [handleCommandSelect]);

  const handleModelSwitched = useCallback(() => {
    setShowModelSelector(false);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-[hsl(240,10%,3.9%)]">
      {/* Header */}
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

          {/* Model Badge - Clickable */}
          <button
            onClick={() => setShowModelSelector(true)}
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

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside
          className={cn(
            'h-full border-r border-[hsl(240,3.7%,15.9%)] flex flex-col transition-all duration-300',
            sidebarCollapsed ? 'w-16' : 'w-64'
          )}
        >
          {/* Sidebar Header */}
          <div className="h-12 flex items-center justify-between px-3 border-b border-[hsl(240,3.7%,15.9%)]">
            {!sidebarCollapsed && (
              <span className="text-sm font-medium text-[hsl(0,0%,98%)]">Navigation</span>
            )}
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="p-1.5 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
            >
              {sidebarCollapsed ? (
                <ChevronRight className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
              ) : (
                <ChevronLeft className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
              )}
            </button>
          </div>

          {/* Nav Items */}
          <nav className="flex-1 p-2 space-y-1">
            <button
              onClick={() => setActiveTab('chat')}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
                activeTab === 'chat'
                  ? 'bg-[hsl(168,100%,50%)]/10 text-[hsl(168,100%,50%)] border border-[hsl(168,100%,50%)]/30'
                  : 'text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)] hover:text-[hsl(0,0%,98%)]'
              )}
            >
              <MessageSquare className="w-5 h-5 flex-shrink-0" />
              {!sidebarCollapsed && <span className="text-sm font-medium">Chat</span>}
            </button>

            <button
              onClick={() => setActiveTab('settings')}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
                activeTab === 'settings'
                  ? 'bg-[hsl(168,100%,50%)]/10 text-[hsl(168,100%,50%)] border border-[hsl(168,100%,50%)]/30'
                  : 'text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)] hover:text-[hsl(0,0%,98%)]'
              )}
            >
              <Settings className="w-5 h-5 flex-shrink-0" />
              {!sidebarCollapsed && <span className="text-sm font-medium">Settings</span>}
            </button>

            <button
              onClick={() => setActiveTab('playground')}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
                activeTab === 'playground'
                  ? 'bg-[hsl(168,100%,50%)]/10 text-[hsl(168,100%,50%)] border border-[hsl(168,100%,50%)]/30'
                  : 'text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)] hover:text-[hsl(0,0%,98%)]'
              )}
            >
              <Wrench className="w-5 h-5 flex-shrink-0" />
              {!sidebarCollapsed && <span className="text-sm font-medium">Tools</span>}
            </button>

            <button
              onClick={() => setShowSkillsPanel(true)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)] hover:text-[hsl(0,0%,98%)]"
            >
              <Code className="w-5 h-5 flex-shrink-0" />
              {!sidebarCollapsed && <span className="text-sm font-medium">Skills</span>}
            </button>

            <button
              onClick={() => setShowTasksPanel(true)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)] hover:text-[hsl(0,0%,98%)]"
            >
              <Bot className="w-5 h-5 flex-shrink-0" />
              {!sidebarCollapsed && <span className="text-sm font-medium">Agent</span>}
            </button>

            <button
              onClick={() => setShowMemoryPanel(true)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)] hover:text-[hsl(0,0%,98%)]"
            >
              <Brain className="w-5 h-5 flex-shrink-0" />
              {!sidebarCollapsed && <span className="text-sm font-medium">Memory</span>}
            </button>
          </nav>

          {/* Session Actions */}
          {!sidebarCollapsed && (
            <div className="p-3 border-t border-[hsl(240,3.7%,15.9%)] space-y-2">
              <button
                onClick={handleNewChat}
                className={cn(
                  'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl',
                  'bg-gradient-to-r from-[hsl(168,100%,50%)] to-[hsl(187,100%,50%)]',
                  'text-[hsl(240,10%,3.9%)] font-medium text-sm',
                  'hover:shadow-[0_0_20px_hsl(168,100%,50%)/0.4] transition-all duration-300'
                )}
              >
                <Plus className="w-4 h-4" />
                新对话
              </button>
              <button
                onClick={() => setShowSessionPanel(true)}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 rounded-lg',
                  'text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)]',
                  'hover:text-[hsl(0,0%,98%)] transition-colors text-sm'
                )}
              >
                <History className="w-4 h-4" />
                历史会话
              </button>
              <button
                onClick={handleClearSession}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 rounded-lg',
                  'text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)]',
                  'hover:text-red-400 transition-colors text-sm'
                )}
              >
                <Trash2 className="w-4 h-4" />
                清空会话
              </button>
            </div>
          )}

        </aside>

        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {activeTab === 'chat' ? (
            <>
              {/* Chat Area */}
              <div className="flex-1 overflow-hidden relative">
                {/* Grid Background */}
                <div className="absolute inset-0 grid-cyber opacity-50" />

                {/* Chat Messages */}
                <div className="relative h-full">
                  <ChatView transcript={transcript} commands={commands} thinking={thinking} />
                </div>
              </div>

              {/* Composer */}
              <div className="border-t border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)]/95 backdrop-blur p-4">
                <div className="max-w-4xl mx-auto">
                  <Composer
                    onSend={handleSend}
                    disabled={!ready}
                    busy={busy}
                    commands={commands}
                  />
                </div>
              </div>
            </>
          ) : activeTab === 'playground' ? (
            <AgentPlayground />
          ) : (
            /* Settings Panel */
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
                        onClick={() => profile.name && handleSwitchProfile(profile.name)}
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
                        onClick={() => setShowModelSelector(true)}
                        className="text-sm font-medium text-[hsl(168,100%,50%)] hover:underline"
                      >
                        {status?.model || 'N/A'}
                      </button>
                    </div>
                    <button
                      onClick={() => setShowModelSelector(true)}
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
                        onClick={() => handleCommandSelect(cmd.replace('/', ''))}
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
                      onClick={() => setTheme('dark')}
                      className={cn(
                        'flex-1 p-4 rounded-lg border transition-all',
                        theme === 'dark'
                          ? 'border-[hsl(168,100%,50%)] bg-[hsl(168,100%,50%)]/10'
                          : 'border-[hsl(240,3.7%,15.9%)] hover:border-[hsl(240,3.7%,25.9%)]'
                      )}
                    >
                      <Moon className="w-5 h-5 mx-auto mb-2 text-[hsl(168,100%,50%)]" />
                      <p className="text-xs font-medium text-center">Dark</p>
                    </button>
                    <button
                      onClick={() => setTheme('light')}
                      className={cn(
                        'flex-1 p-4 rounded-lg border transition-all',
                        theme === 'light'
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
                      onClick={() => handleSend('/toggle-vim')}
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
                      onClick={() => handleSend('/toggle-fast')}
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
                      onClick={() => handleSend('/toggle-voice')}
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
                        onClick={() => handleSend(`/set-effort ${level}`)}
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
                      onClick={() => handleSend('/set-passes -1')}
                      className="w-8 h-8 rounded-lg bg-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,25.9%)] text-[hsl(0,0%,98%)] transition-colors flex items-center justify-center"
                    >
                      <Minus className="w-4 h-4" />
                    </button>
                    <div className="flex-1 text-center">
                      <span className="text-2xl font-bold text-[hsl(168,100%,50%)]">{status?.passes ?? 0}</span>
                      <p className="text-xs text-[hsl(240,5%,64.9%)] mt-1">次迭代</p>
                    </div>
                    <button
                      onClick={() => handleSend('/set-passes 1')}
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
                        onClick={() => handleSend(`/set-permission ${mode.value}`)}
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
          )}
        </main>
      </div>

      {/* Session Panel Slide-out */}
      {showSessionPanel && (
        <div className="fixed inset-0 z-50 flex">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowSessionPanel(false)}
          />
          <div className="relative w-80 bg-[hsl(240,10%,3.9%)] border-r border-[hsl(240,3.7%,15.9%)] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-[hsl(240,3.7%,15.9%)]">
              <h2 className="font-semibold text-[hsl(0,0%,98%)]">历史会话</h2>
              <button
                onClick={() => setShowSessionPanel(false)}
                className="p-1.5 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)]"
              >
                <ChevronRight className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <SessionPanel
                onSelectSession={handleSelectSession}
                onNewChat={handleNewChat}
                currentSessionId={currentSessionId}
              />
            </div>
          </div>
        </div>
      )}

      {/* Model Selector Modal */}
      {showModelSelector && (
        <ModelSelector
          onClose={() => setShowModelSelector(false)}
          onModelSwitched={handleModelSwitched}
        />
      )}

      {/* Skills Panel Modal */}
      {showSkillsPanel && (
        <SkillsPanel
          onClose={() => setShowSkillsPanel(false)}
        />
      )}

      {/* Tasks Panel Modal */}
      {showTasksPanel && (
        <TasksPanel
          onClose={() => setShowTasksPanel(false)}
        />
      )}

      {/* Memory Panel Modal */}
      {showMemoryPanel && (
        <MemoryPanel
          onClose={() => setShowMemoryPanel(false)}
        />
      )}

      {/* Modals */}
      {selectRequest && (
        <SelectModal
          title={selectRequest.title}
          options={selectRequest.options}
          onSelect={(value) => handleSelect(selectRequest.command, value)}
          onClose={clearSelectRequest}
        />
      )}

      {permissionRequest && (
        <PermissionDialog
          toolName={permissionRequest.tool_name}
          reason={permissionRequest.reason}
          onAllow={() => handlePermission(true, permissionRequest.request_id)}
          onDeny={() => handlePermission(false, permissionRequest.request_id)}
        />
      )}
    </div>
  );
}
