import { useState, useEffect } from 'react';
import {
  Search,
  Code,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronRight,
  Terminal,
  Folder,
  Globe,
  Calendar,
  MessageSquare,
  ListTodo,
  Box,
  RefreshCw,
} from 'lucide-react';
import { listTools, executeTool, type Tool } from '../lib/api';
import { cn } from '../lib/utils';

interface ToolCategory {
  name: string;
  icon: React.ReactNode;
  tools: Tool[];
}

const TOOL_CATEGORIES: Record<string, string[]> = {
  '文件操作': ['read_file', 'write_file', 'edit_file', 'glob', 'grep'],
  '搜索': ['web_search', 'tool_search'],
  'Web': ['web_fetch'],
  '任务管理': ['task_create', 'task_list', 'task_get', 'task_update', 'task_stop', 'task_output'],
  '定时任务': ['cron_create', 'cron_list', 'cron_delete', 'cron_toggle'],
  '系统': ['bash', 'config'],
  '会话': ['enter_plan_mode', 'exit_plan_mode', 'enter_worktree', 'exit_worktree'],
  '通信': ['send_message', 'ask_user_question'],
  '其他': ['brief', 'sleep', 'notebook_edit', 'lsp', 'mcp'],
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  '文件操作': <Folder className="w-4 h-4" />,
  '搜索': <Search className="w-4 h-4" />,
  'Web': <Globe className="w-4 h-4" />,
  '任务管理': <ListTodo className="w-4 h-4" />,
  '定时任务': <Calendar className="w-4 h-4" />,
  '系统': <Terminal className="w-4 h-4" />,
  '会话': <Box className="w-4 h-4" />,
  '通信': <MessageSquare className="w-4 h-4" />,
  '其他': <Code className="w-4 h-4" />,
};

export function AgentPlayground() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<{ output: string; is_error: boolean } | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [expandedCategory, setExpandedCategory] = useState<string | null>('文件操作');

  useEffect(() => {
    loadTools();
  }, []);

  const loadTools = async () => {
    setLoading(true);
    try {
      const data = await listTools();
      setTools(data);
    } catch (error) {
      console.error('Failed to load tools:', error);
    } finally {
      setLoading(false);
    }
  };

  const categorizedTools = TOOL_CATEGORIES;
  const categories: ToolCategory[] = Object.entries(categorizedTools).map(([name, toolNames]) => ({
    name,
    icon: CATEGORY_ICONS[name] || <Code className="w-4 h-4" />,
    tools: tools.filter(t => toolNames.includes(t.name)),
  })).filter(c => c.tools.length > 0);

  const filteredCategories = searchQuery
    ? categories.map(cat => ({
        ...cat,
        tools: cat.tools.filter(t =>
          t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          t.description.toLowerCase().includes(searchQuery.toLowerCase())
        ),
      })).filter(c => c.tools.length > 0)
    : categories;

  const handleToolSelect = (tool: Tool) => {
    setSelectedTool(tool);
    setResult(null);
    setFormValues({});

    // Set default values based on tool parameters
    const defaults: Record<string, any> = {};
    if (tool.parameters?.properties) {
      Object.entries(tool.parameters.properties).forEach(([key, prop]: [string, any]) => {
        if (prop.default !== undefined) {
          defaults[key] = prop.default;
        }
      });
    }
    setFormValues(defaults);
  };

  const handleExecute = async () => {
    if (!selectedTool) return;

    setExecuting(true);
    setResult(null);

    try {
      // Parse numeric values
      const args: Record<string, any> = {};
      Object.entries(formValues).forEach(([key, value]) => {
        if (!value && value !== '0') return;
        const prop = selectedTool.parameters?.properties?.[key];
        if (prop?.type === 'integer') {
          args[key] = parseInt(value, 10);
        } else if (prop?.type === 'number') {
          args[key] = parseFloat(value);
        } else {
          args[key] = value;
        }
      });

      const res = await executeTool(selectedTool.name, args);
      setResult({ output: res.output, is_error: res.is_error });
    } catch (error: any) {
      setResult({ output: error.message || '执行失败', is_error: true });
    } finally {
      setExecuting(false);
    }
  };

  const handleFormChange = (key: string, value: string) => {
    setFormValues(prev => ({ ...prev, [key]: value }));
  };

  const getFieldType = (prop: any): string => {
    if (prop.type === 'integer' || prop.type === 'number') return 'number';
    if (prop.type === 'boolean') return 'checkbox';
    return 'text';
  };

  const getFieldDescription = (prop: any): string => {
    return prop.description || prop.title || '';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-[hsl(168,100%,50%)] animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full flex">
      {/* Tool List */}
      <div className="w-80 border-r border-[hsl(240,3.7%,15.9%)] flex flex-col bg-[hsl(240,10%,3.9%)]">
        {/* Search */}
        <div className="p-3 border-b border-[hsl(240,3.7%,15.9%)]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(240,5%,64.9%)]" />
            <input
              type="text"
              placeholder="搜索工具..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-[hsl(240,3.7%,15.9%)] border border-[hsl(240,3.7%,15.9%)] text-sm text-[hsl(0,0%,98%)] placeholder:text-[hsl(240,5%,64.9%)] focus:outline-none focus:border-[hsl(168,100%,50%)]/50"
            />
          </div>
        </div>

        {/* Categories */}
        <div className="flex-1 overflow-y-auto">
          {filteredCategories.map((category) => (
            <div key={category.name} className="border-b border-[hsl(240,3.7%,15.9%)]">
              <button
                onClick={() => setExpandedCategory(expandedCategory === category.name ? null : category.name)}
                className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-[hsl(168,100%,50%)]">{category.icon}</span>
                  <span className="text-sm font-medium text-[hsl(0,0%,98%)]">{category.name}</span>
                </div>
                <ChevronRight
                  className={cn(
                    'w-4 h-4 text-[hsl(240,5%,64.9%)] transition-transform',
                    expandedCategory === category.name && 'rotate-90'
                  )}
                />
              </button>
              {expandedCategory === category.name && (
                <div className="pb-1">
                  {category.tools.map((tool) => (
                    <button
                      key={tool.name}
                      onClick={() => handleToolSelect(tool)}
                      className={cn(
                        'w-full text-left px-3 py-2 transition-colors',
                        selectedTool?.name === tool.name
                          ? 'bg-[hsl(168,100%,50%)]/10 text-[hsl(168,100%,50%)]'
                          : 'hover:bg-[hsl(240,3.7%,15.9%)] text-[hsl(240,5%,64.9%)]'
                      )}
                    >
                      <div className="text-xs font-mono text-[hsl(168,100%,50%)]">{tool.name}</div>
                      <div className="text-xs mt-0.5 line-clamp-1">{tool.description}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Refresh Button */}
        <div className="p-3 border-t border-[hsl(240,3.7%,15.9%)]">
          <button
            onClick={loadTools}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[hsl(240,3.7%,15.9%)] hover:bg-[hsl(240,3.7%,25.9%)] text-sm text-[hsl(240,5%,64.9%)] transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            刷新工具列表
          </button>
        </div>
      </div>

      {/* Tool Detail & Execution */}
      <div className="flex-1 flex flex-col">
        {selectedTool ? (
          <>
            {/* Tool Header */}
            <div className="p-4 border-b border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)]">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[hsl(168,100%,50%)]/10">
                  <Code className="w-5 h-5 text-[hsl(168,100%,50%)]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[hsl(0,0%,98%)]">{selectedTool.name}</h2>
                  <p className="text-sm text-[hsl(240,5%,64.9%)]">{selectedTool.description}</p>
                </div>
              </div>
            </div>

            {/* Parameters Form */}
            <div className="flex-1 overflow-y-auto p-4">
              <div className="max-w-2xl">
                <h3 className="text-sm font-medium text-[hsl(0,0%,98%)] mb-3">参数</h3>
                <div className="space-y-4">
                  {selectedTool.parameters?.properties ? (
                    Object.entries(selectedTool.parameters.properties).map(([key, prop]: [string, any]) => (
                      <div key={key}>
                        <label className="block text-sm font-medium text-[hsl(0,0%,98%)] mb-1">
                          {key}
                          {selectedTool.parameters?.required?.includes(key) && (
                            <span className="text-red-400 ml-1">*</span>
                          )}
                        </label>
                        <p className="text-xs text-[hsl(240,5%,64.9%)] mb-1.5">
                          {getFieldDescription(prop)}
                        </p>
                        {prop.type === 'boolean' ? (
                          <input
                            type="checkbox"
                            checked={formValues[key] === 'true'}
                            onChange={(e) => handleFormChange(key, e.target.checked ? 'true' : 'false')}
                            className="w-4 h-4 rounded border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,3.7%,15.9%)] text-[hsl(168,100%,50%)] focus:ring-[hsl(168,100%,50%)]/50"
                          />
                        ) : (
                          <input
                            type={getFieldType(prop)}
                            value={formValues[key] || ''}
                            onChange={(e) => handleFormChange(key, e.target.value)}
                            placeholder={`Enter ${key}...`}
                            className="w-full px-3 py-2 rounded-lg bg-[hsl(240,3.7%,15.9%)] border border-[hsl(240,3.7%,15.9%)] text-sm text-[hsl(0,0%,98%)] placeholder:text-[hsl(240,5%,64.9%)] focus:outline-none focus:border-[hsl(168,100%,50%)]/50"
                          />
                        )}
                        {prop.type === 'integer' || prop.type === 'number' ? (
                          <p className="text-xs text-[hsl(240,5%,64.9%)] mt-1">
                            {prop.type === 'integer' ? '整数' : '数字'}，范围: {prop.minimum ?? '无'} - {prop.maximum ?? '无'}
                          </p>
                        ) : null}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-[hsl(240,5%,64.9%)]">此工具不需要参数</p>
                  )}
                </div>
              </div>
            </div>

            {/* Result Area */}
            {result && (
              <div className="border-t border-[hsl(240,3.7%,15.9%)] p-4 bg-[hsl(240,10%,3.9%)]">
                <div className="max-w-2xl">
                  <div className="flex items-center gap-2 mb-2">
                    {result.is_error ? (
                      <XCircle className="w-4 h-4 text-red-400" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 text-green-400" />
                    )}
                    <span className={cn(
                      'text-sm font-medium',
                      result.is_error ? 'text-red-400' : 'text-green-400'
                    )}>
                      {result.is_error ? '执行失败' : '执行成功'}
                    </span>
                  </div>
                  <pre className={cn(
                    'p-3 rounded-lg text-xs font-mono overflow-x-auto max-h-64',
                    result.is_error
                      ? 'bg-red-400/10 text-red-300'
                      : 'bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]'
                  )}>
                    {result.output || '(无输出)'}
                  </pre>
                </div>
              </div>
            )}

            {/* Execute Button */}
            <div className="p-4 border-t border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)]">
              <div className="max-w-2xl">
                <button
                  onClick={handleExecute}
                  disabled={executing}
                  className={cn(
                    'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium transition-all',
                    executing
                      ? 'bg-[hsl(240,3.7%,15.9%)] text-[hsl(240,5%,64.9%)] cursor-not-allowed'
                      : 'bg-gradient-to-r from-[hsl(168,100%,50%)] to-[hsl(187,100%,50%)] text-[hsl(240,10%,3.9%)] hover:shadow-[0_0_20px_hsl(168,100%,50%)/0.4]'
                  )}
                >
                  {executing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      执行中...
                    </>
                  ) : (
                    <>
                      <Terminal className="w-4 h-4" />
                      执行工具
                    </>
                  )}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Terminal className="w-12 h-12 mx-auto mb-4 text-[hsl(240,5%,64.9%)] opacity-50" />
              <p className="text-[hsl(240,5%,64.9%)]">从左侧选择一个工具开始体验</p>
              <p className="text-xs text-[hsl(240,5%,64.9%)] mt-2 opacity-70">
                支持文件操作、搜索、Web浏览、任务管理等 {tools.length} 种工具
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
