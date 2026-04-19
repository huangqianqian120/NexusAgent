import { useState, useEffect } from 'react';
import type { SelectOption } from '../types';
import { cn } from '../lib/utils';
import { X, Check } from 'lucide-react';

interface SelectModalProps {
  title: string;
  options: SelectOption[];
  onSelect: (value: string) => void;
  onClose: () => void;
}

export function SelectModal({ title, options, onSelect, onClose }: SelectModalProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((prev) => (prev === 0 ? options.length - 1 : prev - 1));
          break;
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((prev) => (prev === options.length - 1 ? 0 : prev + 1));
          break;
        case 'Enter':
          e.preventDefault();
          onSelect(options[selectedIndex].value);
          break;
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [options, selectedIndex, onSelect, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className={cn(
          'w-full max-w-md mx-4 rounded-2xl border border-[hsl(240,3.7%,15.9%)]',
          'bg-[hsl(240,10%,3.9%)] overflow-hidden',
          'shadow-[0_0_40px_hsl(168,100%,50%)/0.1],0_25rem_3rem_rgba(0,0,0,0.5)'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[hsl(240,3.7%,15.9%)]">
          <h2 className="font-semibold text-[hsl(0,0%,98%)]">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[hsl(240,3.7%,15.9%)] transition-colors"
          >
            <X className="w-4 h-4 text-[hsl(240,5%,64.9%)]" />
          </button>
        </div>

        {/* Options */}
        <div className="p-2 max-h-[300px] overflow-y-auto">
          {options.map((option, index) => (
            <button
              key={option.value}
              onClick={() => onSelect(option.value)}
              onMouseEnter={() => setSelectedIndex(index)}
              className={cn(
                'w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-all duration-200',
                index === selectedIndex
                  ? 'bg-[hsl(168,100%,50%)]/10 border border-[hsl(168,100%,50%)]/30'
                  : 'hover:bg-[hsl(240,3.7%,15.9%)] border border-transparent'
              )}
            >
              <div>
                <div className={cn(
                  'font-medium',
                  index === selectedIndex ? 'text-[hsl(168,100%,50%)]' : 'text-[hsl(0,0%,98%)]'
                )}>
                  {option.label}
                </div>
                {option.description && (
                  <div className="text-xs text-[hsl(240,5%,64.9%)] mt-0.5">
                    {option.description}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {option.active && (
                  <span className="text-[10px] font-medium px-2 py-1 rounded-full bg-[hsl(142,76%,45%)]/10 text-[hsl(142,76%,45%)]">
                    current
                  </span>
                )}
                {index === selectedIndex && (
                  <div className="w-6 h-6 rounded-full bg-[hsl(168,100%,50%)] flex items-center justify-center">
                    <Check className="w-4 h-4 text-[hsl(240,10%,3.9%)]" />
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)]/50">
          <div className="flex items-center gap-4 text-xs text-[hsl(240,5%,64.9%)]">
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 rounded bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]">↑</kbd>
              <kbd className="px-1.5 py-0.5 rounded bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]">↓</kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 rounded bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]">↵</kbd>
              select
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 rounded bg-[hsl(240,3.7%,15.9%)] text-[hsl(0,0%,98%)]">esc</kbd>
              cancel
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
