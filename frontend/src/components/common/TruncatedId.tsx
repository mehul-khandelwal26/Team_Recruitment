import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface TruncatedIdProps {
  id?: string | null;
  prefixLength?: number;
  suffixLength?: number;
  className?: string;
  fallback?: string;
}

export const TruncatedId: React.FC<TruncatedIdProps> = ({
  id,
  prefixLength = 8,
  suffixLength = 4,
  className,
  fallback = '—',
}) => {
  const [copied, setCopied] = useState(false);

  if (!id) {
    return <span className={cn('text-muted-foreground', className)}>{fallback}</span>;
  }

  const shouldTruncate = id.length > prefixLength + suffixLength + 3;
  const displayText = shouldTruncate
    ? `${id.slice(0, prefixLength)}...${id.slice(-suffixLength)}`
    : id;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <span
      className={cn(
        'group inline-flex items-center gap-1.5 font-mono text-xs font-medium text-foreground/90 transition-colors',
        className
      )}
      title={`Click copy to clipboard: ${id}`}
    >
      <span className="truncate">{displayText}</span>
      <button
        type="button"
        onClick={handleCopy}
        className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-0.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-all focus:outline-none focus:ring-1 focus:ring-ring"
        aria-label={`Copy ID ${id}`}
        title="Copy full ID"
      >
        {copied ? (
          <Check className="h-3 w-3 text-emerald-600 animate-in fade-in" />
        ) : (
          <Copy className="h-3 w-3" />
        )}
      </button>
    </span>
  );
};
