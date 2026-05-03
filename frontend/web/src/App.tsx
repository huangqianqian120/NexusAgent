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
import { AppHeader } from './components/AppHeader';
import { AppSidebar } from './components/AppSidebar';
import { AppSettings } from './components/AppSettings';
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

  // 切换到 Settings 标签时拉取 Provider 列表
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
      const newProfiles = await getAllProfiles();
      setProfiles(newProfiles);
    } catch (error) {
      console.error('Failed to switch profile:', error);
    } finally {
      setSwitchingProfile(null);
    }
  }, []);

  const handleNewChat = useCallback(() => {
    sendRequest({ type: 'submit_line', line: '/clear' });
    setCurrentSessionId(undefined);
    setShowSessionPanel(false);
  }, [sendRequest]);

  const handleSelectSession = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
    setShowSessionPanel(false);
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
      <AppHeader
        status={status}
        ready={ready}
        reconnecting={reconnecting}
        theme={theme}
        toggleTheme={toggleTheme}
        onOpenModelSelector={() => setShowModelSelector(true)}
      />

      <div className="flex-1 flex overflow-hidden">
        <AppSidebar
          collapsed={sidebarCollapsed}
          activeTab={activeTab}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onTabChange={setActiveTab}
          onOpenSkills={() => setShowSkillsPanel(true)}
          onOpenTasks={() => setShowTasksPanel(true)}
          onOpenMemory={() => setShowMemoryPanel(true)}
          onNewChat={handleNewChat}
          onOpenSessions={() => setShowSessionPanel(true)}
          onClearSession={handleClearSession}
        />

        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {activeTab === 'chat' ? (
            <>
              <div className="flex-1 overflow-hidden relative">
                <div className="absolute inset-0 grid-cyber opacity-50" />
                <div className="relative h-full">
                  <ChatView transcript={transcript} commands={commands} thinking={thinking} />
                </div>
              </div>
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
            <AppSettings
              status={status}
              commands={commands}
              profiles={profiles}
              switchingProfile={switchingProfile}
              onCommandSelect={handleCommandSelect}
              onSwitchProfile={handleSwitchProfile}
              onSend={handleSend}
              onSetTheme={setTheme}
              onOpenModelSelector={() => setShowModelSelector(true)}
              currentTheme={theme}
            />
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
                <svg className="w-4 h-4 text-[hsl(240,5%,64.9%)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 18l6-6-6-6" />
                </svg>
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

      {/* Select Modal */}
      {selectRequest && (
        <SelectModal
          title={selectRequest.title}
          options={selectRequest.options}
          onSelect={(value) => handleSelect(selectRequest.command, value)}
          onClose={clearSelectRequest}
        />
      )}

      {/* Permission Dialog */}
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
