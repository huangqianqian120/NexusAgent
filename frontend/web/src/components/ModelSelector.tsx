import { useState, useEffect, useCallback } from 'react';
import {
  Bot,
  Check,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { getAvailableModels, getCurrentModel, switchModel, type Model } from '../lib/api';

interface ModelSelectorProps {
  onClose: () => void;
  onModelSwitched: () => void;
}

export function ModelSelector({ onClose, onModelSwitched }: ModelSelectorProps) {
  const [models, setModels] = useState<Model[]>([]);
  const [currentModel, setCurrentModel] = useState('');
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [modelsData] = await Promise.all([
        getAvailableModels(),
        getCurrentModel(),
      ]);
      setModels(modelsData.models);
      setCurrentModel(modelsData.current);
    } catch (err) {
      console.error('Failed to load models:', err);
      setError('加载模型失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const handleSelect = async (model: Model) => {
    if (model.id === currentModel) {
      onClose();
      return;
    }

    setSwitching(model.id);
    try {
      await switchModel(model.id);
      setCurrentModel(model.id);
      onModelSwitched();
      onClose();
    } catch (err) {
      console.error('Failed to switch model:', err);
      setError('切换模型失败');
    } finally {
      setSwitching(null);
    }
  };

  // Group models by type
  const groupedModels = models.reduce((acc, model) => {
    const key = model.description.includes('Allowed') ? 'custom' : 'preset';
    if (!acc[key]) acc[key] = [];
    acc[key].push(model);
    return acc;
  }, {} as Record<string, Model[]>);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className={cn(
          'w-full max-w-lg mx-4 rounded-2xl border border-[hsl(240,3.7%,15.9%)]',
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
              <h2 className="font-semibold text-[hsl(0,0%,98%)]">选择模型</h2>
              <p className="text-xs text-[hsl(240,5%,64.9%)]">选择要使用的 AI 模型</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
          >
            <svg className="w-5 h-5 text-[hsl(240,5%,64.9%)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-4 max-h-[400px] overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-[hsl(168,100%,50%)] animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-8 text-red-400 text-sm">{error}</div>
          ) : (
            <div className="space-y-4">
              {/* Current Model */}
              <div className="px-3 py-2 rounded-xl bg-[hsl(168,100%,50%)]/10 border border-[hsl(168,100%,50%)]/30">
                <div className="flex items-center gap-2 text-xs text-[hsl(168,100%,50%)] mb-1">
                  <Sparkles className="w-3 h-3" />
                  当前模型
                </div>
                <p className="font-medium text-[hsl(0,0%,98%)]">{currentModel}</p>
              </div>

              {/* Preset Models */}
              {groupedModels.preset && groupedModels.preset.length > 0 && (
                <div>
                  <h3 className="text-xs font-medium text-[hsl(240,5%,64.9%)] uppercase tracking-wider px-3 mb-2">
                    推荐模型
                  </h3>
                  <div className="space-y-1">
                    {groupedModels.preset.map((model) => (
                      <button
                        key={model.id}
                        onClick={() => handleSelect(model)}
                        disabled={switching !== null}
                        className={cn(
                          'w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-all duration-200',
                          model.id === currentModel
                            ? 'bg-[hsl(168,100%,50%)]/10 border border-[hsl(168,100%,50%)]/30'
                            : 'hover:bg-[hsl(240,3.7%,15.9%)] border border-transparent'
                        )}
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-[hsl(0,0%,98%)]">{model.name}</span>
                            {model.id === currentModel && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[hsl(168,100%,50%)]/20 text-[hsl(168,100%,50%)]">
                                当前
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-[hsl(240,5%,64.9%)] mt-0.5">{model.description}</p>
                        </div>
                        {switching === model.id ? (
                          <Loader2 className="w-4 h-4 text-[hsl(168,100%,50%)] animate-spin" />
                        ) : model.id === currentModel ? (
                          <div className="w-5 h-5 rounded-full bg-[hsl(168,100%,50%)] flex items-center justify-center">
                            <Check className="w-3 h-3 text-[hsl(240,10%,3.9%)]" />
                          </div>
                        ) : null}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Custom Models */}
              {groupedModels.custom && groupedModels.custom.length > 0 && (
                <div>
                  <h3 className="text-xs font-medium text-[hsl(240,5%,64.9%)] uppercase tracking-wider px-3 mb-2">
                    自定义模型
                  </h3>
                  <div className="space-y-1">
                    {groupedModels.custom.map((model) => (
                      <button
                        key={model.id}
                        onClick={() => handleSelect(model)}
                        disabled={switching !== null}
                        className={cn(
                          'w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-all duration-200',
                          model.id === currentModel
                            ? 'bg-[hsl(168,100%,50%)]/10 border border-[hsl(168,100%,50%)]/30'
                            : 'hover:bg-[hsl(240,3.7%,15.9%)] border border-transparent'
                        )}
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-[hsl(0,0%,98%)]">{model.name}</span>
                          </div>
                          <p className="text-xs text-[hsl(240,5%,64.9%)] mt-0.5">{model.description}</p>
                        </div>
                        {switching === model.id ? (
                          <Loader2 className="w-4 h-4 text-[hsl(168,100%,50%)] animate-spin" />
                        ) : model.id === currentModel ? (
                          <div className="w-5 h-5 rounded-full bg-[hsl(168,100%,50%)] flex items-center justify-center">
                            <Check className="w-3 h-3 text-[hsl(240,10%,3.9%)]" />
                          </div>
                        ) : null}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)]/50">
          <p className="text-xs text-[hsl(240,5%,64.9%)] text-center">
            选择模型后，新的对话将使用该模型
          </p>
        </div>
      </div>
    </div>
  );
}
