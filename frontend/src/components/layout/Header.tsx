import React from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, Activity, Database, AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { API_BASE_URL } from '@/lib/api-client';
import { useBackendHealth } from '@/hooks/useDashboard';
import { cn } from '@/lib/utils';

interface HeaderProps {
  onMenuClick: () => void;
}

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  '/': {
    title: 'Recruitment Dashboard',
    subtitle: 'Overview of datasets, recent evaluation runs, and organizer activity',
  },
  '/evaluate': {
    title: 'New Candidate Evaluation',
    subtitle: 'Multi-stage candidate shortlisting pipeline across datasets and signals',
  },
  '/results': {
    title: 'Evaluation Results & Shortlists',
    subtitle: 'Top-X shortlisted teams, eligibility verdicts, and explainability audit trails',
  },
  '/configurations': {
    title: 'Rules & Scoring Configurations',
    subtitle: 'Manage versioned eligibility rule sets and multi-criteria scoring weights',
  },
};

export const Header: React.FC<HeaderProps> = ({ onMenuClick }) => {
  const location = useLocation();
  const currentMeta = PAGE_META[location.pathname] || {
    title: 'Team Recruitment Automation Tool',
    subtitle: 'Hackathon evaluation and shortlisting platform',
  };

  const {
    data: health,
    isLoading: isHealthLoading,
    isError: isHealthError,
    refetch: refetchHealth,
    isFetching: isHealthFetching,
  } = useBackendHealth();

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between border-b border-border bg-card/90 px-4 backdrop-blur-xs sm:px-6">
      {/* Left Title Area */}
      <div className="flex items-center gap-3 min-w-0">
        <Button
          variant="outline"
          size="icon"
          className="h-9 w-9 shrink-0 md:hidden"
          onClick={onMenuClick}
          aria-label="Toggle navigation menu"
        >
          <Menu className="h-4 w-4" />
        </Button>

        <div className="flex flex-col min-w-0">
          <h1 className="text-base sm:text-lg font-semibold tracking-tight text-foreground truncate">
            {currentMeta.title}
          </h1>
          <p className="hidden sm:block text-xs text-muted-foreground truncate">
            {currentMeta.subtitle}
          </p>
        </div>
      </div>

      {/* Right Environment Context & Badges */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        <div className="hidden lg:flex items-center gap-2 text-xs text-muted-foreground bg-secondary/50 px-2.5 py-1 rounded border border-border/80">
          <Database className="h-3.5 w-3.5 text-forest-700" />
          <span className="font-mono text-[11px] truncate max-w-[200px]" title={API_BASE_URL}>
            {API_BASE_URL}
          </span>
        </div>

        {/* Live Health Status from /api/health */}
        {isHealthLoading ? (
          <Badge variant="outline" className="gap-1.5 font-mono text-[11px] py-0.5 text-muted-foreground">
            <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
            <span className="hidden sm:inline">Connecting...</span>
          </Badge>
        ) : isHealthError ? (
          <div className="flex items-center gap-1.5">
            <Badge variant="destructive" className="gap-1.5 font-mono text-[11px] py-0.5">
              <AlertCircle className="h-3 w-3" />
              <span>Backend Offline</span>
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-foreground"
              onClick={() => refetchHealth()}
              title="Retry backend health check"
              disabled={isHealthFetching}
            >
              <RefreshCw className={cn('h-3 w-3', isHealthFetching && 'animate-spin')} />
            </Button>
          </div>
        ) : (
          <Badge
            variant="success"
            className="gap-1.5 font-mono text-[11px] py-0.5 cursor-help"
            title={`Backend v${health?.version || '1.0.0'} (${health?.environment || 'development'}) | Storage: ${health?.storage_backend || 'memory'}`}
          >
            <Activity className="h-3 w-3 animate-pulse text-emerald-600" />
            <span className="hidden sm:inline">Backend</span> Live
            {health?.storage_backend && (
              <span className="text-[10px] opacity-80 font-mono pl-1 ml-0.5 border-l border-emerald-300">
                {health.storage_backend}
              </span>
            )}
          </Badge>
        )}
      </div>
    </header>
  );
};
