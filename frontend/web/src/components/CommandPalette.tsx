import { useState, useEffect, useRef } from 'react';
import { Search } from 'lucide-react';
import { cn } from '../lib/utils';

interface Command {
  name: string;
  description: string;
}

interface CommandPaletteProps {
  commands: Command[];
  onSelect: (command: string) => void;
  onClose: () => void;
}

export function CommandPalette({ commands, onSelect, onClose }: CommandPaletteProps) {
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredCommands = commands.filter(
    (cmd) =>
      cmd.name.toLowerCase().includes(search.toLowerCase()) ||
      cmd.description.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    setSelectedIndex(0);
  }, [search]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, filteredCommands.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredCommands[selectedIndex]) {
        onSelect(filteredCommands[selectedIndex].name);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  return (
    <div className="absolute bottom-full left-0 right-0 mb-2">
      <div
        className="rounded-xl border border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)] shadow-xl overflow-hidden"
        onKeyDown={handleKeyDown}
      >
        {/* Search Input */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[hsl(240,3.7%,15.9%)]">
          <Search className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索命令..."
            className="flex-1 bg-transparent text-sm text-[hsl(0,0%,98%)] placeholder:text-[hsl(240,5%,64.9%)] focus:outline-none"
          />
        </div>

        {/* Command List */}
        <div className="max-h-64 overflow-y-auto">
          {filteredCommands.length === 0 ? (
            <div className="px-3 py-4 text-center text-sm text-[hsl(240,5%,64.9%)]">
              没有找到匹配的命令
            </div>
          ) : (
            filteredCommands.map((cmd, index) => (
              <button
                key={cmd.name}
                onClick={() => onSelect(cmd.name)}
                className={cn(
                  'w-full px-3 py-2 flex items-start gap-3 text-left transition-colors',
                  index === selectedIndex
                    ? 'bg-[hsl(168,100%,50%)]/10 text-[hsl(168,100%,50%)]'
                    : 'hover:bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]'
                )}
              >
                <span className="font-mono text-sm text-[hsl(168,100%,50%)]">{cmd.name}</span>
                <span className="text-xs text-[hsl(240,5%,64.9%)]">{cmd.description}</span>
              </button>
            ))
          )}
        </div>

        {/* Footer Hint */}
        <div className="px-3 py-2 border-t border-[hsl(240,3.7%,15.9%)] text-xs text-[hsl(240,5%,64.9%)]">
          <span className="mr-2">↑↓</span> 导航
          <span className="mx-2">↵</span> 选择
          <span className="mx-2">Esc</span> 关闭
        </div>
      </div>
    </div>
  );
}
