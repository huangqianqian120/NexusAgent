import {
  MessageSquare, Settings, ChevronLeft, ChevronRight,
  History, Trash2, Plus, Code, Wrench, Bot, Brain,
} from 'lucide-react';
import { cn } from '../lib/utils';

type ActiveTab = 'chat' | 'settings' | 'playground';

interface AppSidebarProps {
  collapsed: boolean;
  activeTab: ActiveTab;
  onToggleCollapse: () => void;
  onTabChange: (tab: ActiveTab) => void;
  onOpenSkills: () => void;
  onOpenTasks: () => void;
  onOpenMemory: () => void;
  onNewChat: () => void;
  onOpenSessions: () => void;
  onClearSession: () => void;
}

export function AppSidebar({
  collapsed,
  activeTab,
  onToggleCollapse,
  onTabChange,
  onOpenSkills,
  onOpenTasks,
  onOpenMemory,
  onNewChat,
  onOpenSessions,
  onClearSession,
}: AppSidebarProps) {
  return (
    <aside
      className={cn(
        'h-full border-r border-[hsl(240,3.7%,15.9%)] flex flex-col transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Sidebar Header */}
      <div className="h-12 flex items-center justify-between px-3 border-b border-[hsl(240,3.7%,15.9%)]">
        {!collapsed && <span className="text-sm font-medium text-[hsl(0,0%,98%)]">Navigation</span>}
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
          ) : (
            <ChevronLeft className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
          )}
        </button>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 p-2 space-y-1">
        <NavButton
          icon={<MessageSquare className="w-5 h-5 flex-shrink-0" />}
          label="Chat"
          active={activeTab === 'chat'}
          collapsed={collapsed}
          onClick={() => onTabChange('chat')}
        />
        <NavButton
          icon={<Settings className="w-5 h-5 flex-shrink-0" />}
          label="Settings"
          active={activeTab === 'settings'}
          collapsed={collapsed}
          onClick={() => onTabChange('settings')}
        />
        <NavButton
          icon={<Wrench className="w-5 h-5 flex-shrink-0" />}
          label="Tools"
          active={activeTab === 'playground'}
          collapsed={collapsed}
          onClick={() => onTabChange('playground')}
        />
        <NavButton
          icon={<Code className="w-5 h-5 flex-shrink-0" />}
          label="Skills"
          active={false}
          collapsed={collapsed}
          onClick={onOpenSkills}
        />
        <NavButton
          icon={<Bot className="w-5 h-5 flex-shrink-0" />}
          label="Agent"
          active={false}
          collapsed={collapsed}
          onClick={onOpenTasks}
        />
        <NavButton
          icon={<Brain className="w-5 h-5 flex-shrink-0" />}
          label="Memory"
          active={false}
          collapsed={collapsed}
          onClick={onOpenMemory}
        />
      </nav>

      {/* Session Actions */}
      {!collapsed && (
        <div className="p-3 border-t border-[hsl(240,3.7%,15.9%)] space-y-2">
          <button
            onClick={onNewChat}
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
            onClick={onOpenSessions}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)] hover:text-[hsl(0,0%,98%)] transition-colors text-sm"
          >
            <History className="w-4 h-4" />
            历史会话
          </button>
          <button
            onClick={onClearSession}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)] hover:text-red-400 transition-colors text-sm"
          >
            <Trash2 className="w-4 h-4" />
            清空会话
          </button>
        </div>
      )}
    </aside>
  );
}

function NavButton({
  icon,
  label,
  active,
  collapsed,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  collapsed: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
        active
          ? 'bg-[hsl(168,100%,50%)]/10 text-[hsl(168,100%,50%)] border border-[hsl(168,100%,50%)]/30'
          : 'text-[hsl(240,5%,64.9%)] hover:bg-[hsl(240,3.7%,15.9%)] hover:text-[hsl(0,0%,98%)]'
      )}
    >
      {icon}
      {!collapsed && <span className="text-sm font-medium">{label}</span>}
    </button>
  );
}
