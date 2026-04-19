import { AlertTriangle, X, Check } from 'lucide-react';
import { cn } from '../lib/utils';

interface PermissionDialogProps {
  toolName: string;
  reason: string;
  onAllow: () => void;
  onDeny: () => void;
}

export function PermissionDialog({
  toolName,
  reason,
  onAllow,
  onDeny,
}: PermissionDialogProps) {
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
        <div className="flex items-center gap-4 px-6 py-5 border-b border-[hsl(240,3.7%,15.9%)]">
          <div className="w-12 h-12 rounded-xl bg-yellow-500/10 flex items-center justify-center">
            <AlertTriangle className="w-6 h-6 text-yellow-400" />
          </div>
          <div>
            <h2 className="font-semibold text-lg text-[hsl(0,0%,98%)]">Permission Required</h2>
            <p className="text-sm text-[hsl(240,5%,64.9%)]">Tool execution request</p>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-[hsl(240,5%,64.9%)] uppercase tracking-wider">Tool</span>
            </div>
            <div className="px-4 py-3 rounded-xl bg-[hsl(240,3.7%,15.9%)] border border-[hsl(240,3.7%,15.9%)]">
              <code className="text-sm font-mono text-[hsl(168,100%,50%)]">{toolName}</code>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-[hsl(240,5%,64.9%)] uppercase tracking-wider">Reason</span>
            </div>
            <div className="px-4 py-3 rounded-xl bg-[hsl(240,3.7%,15.9%)] border border-[hsl(240,3.7%,15.9%)]">
              <p className="text-sm text-[hsl(0,0%,98%)] leading-relaxed">{reason}</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-4 border-t border-[hsl(240,3.7%,15.9%)] bg-[hsl(240,10%,3.9%)]/50">
          <button
            onClick={onDeny}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl',
              'border border-[hsl(240,3.7%,15.9%)] bg-transparent',
              'text-[hsl(0,0%,98%)] hover:bg-[hsl(240,3.7%,15.9%)]',
              'transition-all duration-200'
            )}
          >
            <X className="w-4 h-4" />
            <span className="font-medium">Deny</span>
          </button>
          <button
            onClick={onAllow}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl',
              'bg-gradient-to-r from-[hsl(168,100%,50%)] to-[hsl(187,100%,50%)]',
              'text-[hsl(240,10%,3.9%)] font-medium',
              'hover:shadow-[0_0_20px_hsl(168,100%,50%)/0.4]',
              'transition-all duration-300'
            )}
          >
            <Check className="w-4 h-4" />
            <span>Allow</span>
          </button>
        </div>
      </div>
    </div>
  );
}
