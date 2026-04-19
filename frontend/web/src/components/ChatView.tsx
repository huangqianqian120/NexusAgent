import { useEffect, useRef } from 'react';
import { MessageBubble } from './MessageBubble';
import { Code, FileText, MemoryStick, Users, Zap, Settings } from 'lucide-react';
import type { TranscriptItem } from '../types';

interface ChatViewProps {
  transcript: TranscriptItem[];
  commands?: string[];
  thinking?: boolean;
}

const CAPABILITIES = [
  { icon: Code, title: '代码助手', desc: '编写、重构、调试代码' },
  { icon: FileText, title: '文件操作', desc: '读取、编辑、搜索文件' },
  { icon: MemoryStick, title: '记忆管理', desc: '跨会话保持上下文' },
  { icon: Users, title: '多Agent协作', desc: '协调多个AI Agent任务' },
  { icon: Zap, title: '技能扩展', desc: '加载自定义技能和工作流' },
  { icon: Settings, title: '灵活配置', desc: '支持多种模型和提供商' },
];

export function ChatView({ transcript, commands = [], thinking = false }: ChatViewProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript, thinking]);

  if (transcript.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center overflow-y-auto pt-20">
        <div className="text-center mb-8">
          <h2 className="text-xl font-semibold mb-2 cyber-glow-text text-[hsl(168,100%,50%)]">
            欢迎使用 NexusAgent
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-w-3xl px-4">
          {CAPABILITIES.map((cap, i) => (
            <div
              key={i}
              className="flex items-start gap-3 p-3 rounded-xl bg-[hsl(240,3.7%,15.9%)]/50 border border-[hsl(240,3.7%,15.9%)] hover:border-[hsl(168,100%,50%)]/30 transition-all"
            >
              <div className="w-8 h-8 rounded-lg bg-[hsl(168,100%,50%)]/10 flex items-center justify-center flex-shrink-0">
                <cap.icon className="w-4 h-4 text-[hsl(168,100%,50%)]" />
              </div>
              <div className="text-left">
                <p className="text-sm font-medium text-[hsl(0,0%,98%)]">{cap.title}</p>
                <p className="text-xs text-[hsl(240,5%,64.9%)]">{cap.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {commands.length > 0 && (
          <div className="mt-6 px-4">
            <p className="text-xs text-[hsl(240,5%,64.9%)] mb-2">输入 <kbd className="px-1.5 py-0.5 rounded bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]">/</kbd> 使用命令</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
      {transcript.map((item, index) => (
        <MessageBubble key={index} item={item} />
      ))}
      {thinking && transcript.length > 0 && (
        <div className="flex items-center gap-2 text-[hsl(240,5%,64.9%)]">
          <div className="flex gap-1">
            <span className="w-2 h-2 rounded-full bg-[hsl(168,100%,50%)] animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 rounded-full bg-[hsl(168,100%,50%)] animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 rounded-full bg-[hsl(168,100%,50%)] animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-sm">正在思考...</span>
        </div>
      )}
    </div>
  );
}
