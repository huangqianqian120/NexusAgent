import { useState, useEffect, useCallback } from 'react';
import {
  Brain,
  X,
  Loader2,
  Search,
  FileText,
  ChevronDown,
  ChevronRight,
  FolderOpen,
} from 'lucide-react';
import { cn } from '../lib/utils';
import {
  listMemories,
  queryMemories,
  type MemoryEntry,
} from '../lib/api';

interface MemoryPanelProps {
  onClose: () => void;
}

const memoryTypeLabels: Record<string, string> = {
  fact: '事实',
  episode: '事件',
  preference: '偏好',
  procedure: '流程',
};

const memoryTypeColors: Record<string, string> = {
  fact: 'bg-blue-500/10 text-blue-400',
  episode: 'bg-purple-500/10 text-purple-400',
  preference: 'bg-green-500/10 text-green-400',
  procedure: 'bg-orange-500/10 text-orange-400',
};

export function MemoryPanel({ onClose }: MemoryPanelProps) {
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedMemory, setExpandedMemory] = useState<string | null>(null);

  const loadMemories = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listMemories();
      setMemories(data.memories || []);
    } catch (err) {
      console.error('Failed to load memories:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMemories();
  }, [loadMemories]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadMemories();
      return;
    }
    setLoading(true);
    try {
      const result = await queryMemories({
        text: searchQuery,
        limit: 20,
        budget_tokens: 10000,
      });
      setMemories(result.entries);
    } catch (err) {
      console.error('Failed to search memories:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExpand = async (memoryId: string) => {
    if (expandedMemory === memoryId) {
      setExpandedMemory(null);
      return;
    }
    setExpandedMemory(memoryId);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
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
          'shadow-[0_0_40px_hsl(168,100%,50%)/0.1],0_25rem_3rem_rgba(0,0,0,0.5)',
          'max-h-[80vh] flex flex-col'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[hsl(240,3.7%,15.9%)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[hsl(168,100%,50%)]/10 flex items-center justify-center">
              <Brain className="w-5 h-5 text-[hsl(168,100%,50%)]" />
            </div>
            <div>
              <h2 className="font-semibold text-[hsl(0,0%,98%)]">记忆中心</h2>
              <p className="text-xs text-[hsl(240,5%,64.9%)]">AI 的长期记忆存储</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
          >
            <X className="w-5 h-5 text-[hsl(240,5%,64.9%)]" />
          </button>
        </div>

        {/* Search */}
        <div className="px-6 py-4 border-b border-[hsl(240,3.7%,15.9%)]">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(240,5%,64.9%)]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="搜索记忆..."
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-[hsl(240,3.7%,15.9%)] border border-[hsl(240,3.7%,25.9%)] text-[hsl(0,0%,98%)] text-sm focus:outline-none focus:border-[hsl(168,100%,50%)]"
              />
            </div>
            <button
              onClick={handleSearch}
              className="px-4 py-2 rounded-lg bg-[hsl(168,100%,50%)] hover:bg-[hsl(168,100%,45%)] text-black text-sm font-medium transition-colors"
            >
              搜索
            </button>
          </div>
        </div>

        {/* Memory List */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-[hsl(168,100%,50%)] animate-spin" />
            </div>
          ) : memories.length === 0 ? (
            <div className="text-center py-8 text-[hsl(240,5%,64.9%)] text-sm">
              暂无记忆
            </div>
          ) : (
            <div className="space-y-2">
              {memories.map((memory) => (
                <div
                  key={memory.id}
                  className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,3.7%,15.9%)]/50 overflow-hidden"
                >
                  <div
                    className="flex items-center gap-3 p-4 cursor-pointer hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
                    onClick={() => handleExpand(memory.id)}
                  >
                    <div className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                      memoryTypeColors[memory.memory_type]
                    )}>
                      <FileText className="w-4 h-4" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-[hsl(0,0%,98%)] truncate">
                          {memory.name}
                        </p>
                        <span className={cn(
                          'px-2 py-0.5 rounded text-[10px] font-medium',
                          memoryTypeColors[memory.memory_type]
                        )}>
                          {memoryTypeLabels[memory.memory_type]}
                        </span>
                      </div>
                      <p className="text-xs text-[hsl(240,5%,64.9%)] truncate mt-1">
                        {memory.summary || '无描述'}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs text-[hsl(240,5%,64.9%)]">
                        {formatDate(memory.updated_at)}
                      </span>
                      {expandedMemory === memory.id ? (
                        <ChevronDown className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
                      )}
                    </div>
                  </div>

                  {expandedMemory === memory.id && (
                    <div className="border-t border-[hsl(240,3.7%,15.9%)] p-4 bg-[hsl(240,10%,3.9%)]/50">
                      {memory.tags.length > 0 && (
                        <div className="flex items-center gap-1 mb-3 flex-wrap">
                          {memory.tags.map((tag) => (
                            <span
                              key={tag}
                              className="px-2 py-0.5 rounded text-[10px] bg-[hsl(240,3.7%,25.9%)] text-[hsl(240,5%,64.9%)]"
                            >
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
                      <pre className="text-xs font-mono text-[hsl(0,0%,98%)] bg-[hsl(240,3.7%,15.9%)] rounded-lg p-3 max-h-40 overflow-auto whitespace-pre-wrap">
                        {memory.summary || '(无内容)'}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[hsl(240,3.7%,15.9%)]">
          <div className="flex items-center justify-between text-xs text-[hsl(240,5%,64.9%)]">
            <span>{memories.length} 个记忆</span>
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                // Open memory directory in file manager or editor
                alert('记忆文件位于项目目录的 .nexus/memory/ 文件夹中，可直接在编辑器中修改');
              }}
              className="flex items-center gap-1 hover:text-[hsl(168,100%,50%)] transition-colors"
            >
              <FolderOpen className="w-3 h-3" />
              在编辑器中修改
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
