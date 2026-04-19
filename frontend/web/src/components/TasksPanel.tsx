import { useState, useEffect, useCallback } from 'react';
import {
  Bot,
  Terminal,
  Loader2,
  X,
  ChevronDown,
  ChevronRight,
  Copy,
  CheckCircle,
  XCircle,
  Clock,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { listTasks, getTaskOutput, stopTask, type Task } from '../lib/api';

interface TasksPanelProps {
  onClose: () => void;
}

export function TasksPanel({ onClose }: TasksPanelProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTask, setExpandedTask] = useState<string | null>(null);
  const [taskOutput, setTaskOutput] = useState<Record<string, string>>({});
  const [loadingOutput, setLoadingOutput] = useState<string | null>(null);
  const [stopping, setStopping] = useState<string | null>(null);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listTasks();
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
    // Refresh every 5 seconds
    const interval = setInterval(loadTasks, 5000);
    return () => clearInterval(interval);
  }, [loadTasks]);

  const handleExpand = async (taskId: string) => {
    if (expandedTask === taskId) {
      setExpandedTask(null);
      return;
    }

    setExpandedTask(taskId);

    if (!taskOutput[taskId]) {
      setLoadingOutput(taskId);
      try {
        const output = await getTaskOutput(taskId);
        setTaskOutput(prev => ({ ...prev, [taskId]: output.output }));
      } catch (error) {
        console.error('Failed to load task output:', error);
        setTaskOutput(prev => ({ ...prev, [taskId]: 'Failed to load output' }));
      } finally {
        setLoadingOutput(null);
      }
    }
  };

  const handleStop = async (taskId: string) => {
    setStopping(taskId);
    try {
      await stopTask(taskId);
      setTasks(prev => prev.map(t =>
        t.id === taskId ? { ...t, status: 'stopped' } : t
      ));
    } catch (error) {
      console.error('Failed to stop task:', error);
    } finally {
      setStopping(null);
    }
  };

  const handleCopyOutput = (output: string) => {
    navigator.clipboard.writeText(output);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Clock className="w-4 h-4 text-blue-400" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'stopped':
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'local_agent':
        return <Bot className="w-4 h-4" />;
      case 'local_bash':
      default:
        return <Terminal className="w-4 h-4" />;
    }
  };

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className={cn(
          'w-full max-w-3xl mx-4 rounded-2xl border border-[hsl(240,3.7%,15.9%)]',
          'bg-[hsl(240,10%,3.9%)] overflow-hidden',
          'shadow-[0_0_40px_hsl(168,100%,50%)/0.1],0_25rem_3rem_rgba(0,0,0,0.5)'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[hsl(240,3.7%,15.9%)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[hsl(168,100%,50%)]/10 flex items-center justify-center">
              <Bot className="w-5 h-5 text-[hsl(168,100%,50%)]" />
            </div>
            <div>
              <h2 className="font-semibold text-[hsl(0,0%,98%)]">Agent / 任务管理</h2>
              <p className="text-xs text-[hsl(240,5%,64.9%)]">查看和管理后台运行的 Agent 和任务</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
          >
            <X className="w-5 h-5 text-[hsl(240,5%,64.9%)]" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-[hsl(168,100%,50%)] animate-spin" />
            </div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-8 text-[hsl(240,5%,64.9%)] text-sm">
              暂无运行中的任务
            </div>
          ) : (
            <div className="space-y-2">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,3.7%,15.9%)]/50 overflow-hidden"
                >
                  {/* Task Header */}
                  <div
                    className="flex items-center gap-3 p-4 cursor-pointer hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
                    onClick={() => handleExpand(task.id)}
                  >
                    <div className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                      task.type === 'local_agent'
                        ? 'bg-purple-500/10 text-purple-400'
                        : 'bg-blue-500/10 text-blue-400'
                    )}>
                      {getTypeIcon(task.type)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-[hsl(0,0%,98%)] truncate">
                          {task.description || task.id}
                        </p>
                        {getStatusIcon(task.status)}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-[hsl(240,5%,64.9%)]">
                          {task.type === 'local_agent' ? 'Agent' : 'Shell'}
                        </span>
                        <span className="text-xs text-[hsl(240,5%,64.9%)]">·</span>
                        <span className="text-xs text-[hsl(240,5%,64.9%)]">
                          {formatTime(task.created_at)}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {task.status === 'running' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStop(task.id);
                          }}
                          disabled={stopping === task.id}
                          className="p-2 rounded-lg hover:bg-red-500/10 text-red-400 transition-colors"
                          title="停止任务"
                        >
                          {stopping === task.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <XCircle className="w-4 h-4" />
                          )}
                        </button>
                      )}
                      {expandedTask === task.id ? (
                        <ChevronDown className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
                      )}
                    </div>
                  </div>

                  {/* Task Details */}
                  {expandedTask === task.id && (
                    <div className="border-t border-[hsl(240,3.7%,15.9%)] p-4 bg-[hsl(240,10%,3.9%)]/50">
                      {/* Task Info */}
                      <div className="grid grid-cols-2 gap-4 mb-4 text-xs">
                        <div>
                          <span className="text-[hsl(240,5%,64.9%)]">ID:</span>
                          <span className="ml-2 text-[hsl(0,0%,98%)] font-mono">{task.id}</span>
                        </div>
                        <div>
                          <span className="text-[hsl(240,5%,64.9%)]">状态:</span>
                          <span className={cn(
                            'ml-2',
                            task.status === 'running' ? 'text-blue-400' :
                            task.status === 'completed' ? 'text-green-400' : 'text-red-400'
                          )}>
                            {task.status}
                          </span>
                        </div>
                        <div className="col-span-2">
                          <span className="text-[hsl(240,5%,64.9%)]">工作目录:</span>
                          <span className="ml-2 text-[hsl(0,0%,98%)] font-mono truncate">{task.cwd}</span>
                        </div>
                        {task.command && (
                          <div className="col-span-2">
                            <span className="text-[hsl(240,5%,64.9%)]">命令:</span>
                            <span className="ml-2 text-[hsl(0,0%,98%)] font-mono text-xs break-all">{task.command}</span>
                          </div>
                        )}
                        {task.prompt && (
                          <div className="col-span-2">
                            <span className="text-[hsl(240,5%,64.9%)]">Prompt:</span>
                            <p className="mt-1 text-[hsl(0,0%,98%)] text-xs bg-[hsl(240,3.7%,15.9%)] rounded-lg p-2 max-h-24 overflow-y-auto">
                              {task.prompt}
                            </p>
                          </div>
                        )}
                      </div>

                      {/* Output */}
                      <div className="border-t border-[hsl(240,3.7%,15.9%)] pt-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-medium text-[hsl(0,0%,98%)]">输出日志</span>
                          <button
                            onClick={() => handleCopyOutput(taskOutput[task.id] || '')}
                            className="p-1 rounded hover:bg-[hsl(240,3.7%,15.9%)] text-[hsl(240,5%,64.9%)] hover:text-[hsl(168,100%,50%)]"
                            title="复制输出"
                          >
                            <Copy className="w-3 h-3" />
                          </button>
                        </div>
                        {loadingOutput === task.id ? (
                          <div className="flex items-center justify-center py-4">
                            <Loader2 className="w-4 h-4 text-[hsl(168,100%,50%)] animate-spin" />
                          </div>
                        ) : (
                          <pre className="text-xs font-mono text-[hsl(0,0%,98%)] bg-[hsl(240,3.7%,15.9%)] rounded-lg p-3 max-h-48 overflow-auto whitespace-pre-wrap">
                            {taskOutput[task.id] || '(无输出)'}
                          </pre>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)]/50">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[hsl(240,5%,64.9%)]">
              {tasks.length} 个任务
              {tasks.filter(t => t.status === 'running').length > 0 && (
                <span className="ml-2 text-blue-400">
                  · {tasks.filter(t => t.status === 'running').length} 运行中
                </span>
              )}
            </span>
            <button
              onClick={loadTasks}
              className="px-3 py-1.5 rounded-lg bg-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,25.9%)] text-xs text-[hsl(240,5%,64.9%)] transition-colors"
            >
              刷新
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
