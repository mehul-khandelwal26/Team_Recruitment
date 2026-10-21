import React from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, AlertCircle, RefreshCw, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useBackendHealth } from '@/hooks/useDashboard';
import { useAuth } from '@/context/AuthContext';
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
  const { user, authStatus, logout } = useAuth();
  const currentMeta = PAGE_META[location.pathname] || {
    title: 'Team Recruitment Automation Tool',
    subtitle: 'Hackathon evaluation and shortlisting platform',
  };

  const {
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

      {/* Right Environment Context, Health & User Profile */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
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
          <div
            className="flex items-center gap-2 px-2.5 py-1 rounded-full border border-border/80 bg-secondary/40 text-xs font-medium text-muted-foreground cursor-default transition-colors"
            title="System Operational · All services online"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[11px] font-medium text-foreground/80">System Operational</span>
          </div>
        )}

        {/* Authenticated User Profile & Sign Out */}
        {user && (
          <div className="flex items-center gap-2 pl-2 border-l border-border/80">
            <div
              className="flex items-center gap-2"
              title={`${user.full_name} (${user.email})`}
            >
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={user.full_name}
                  className="h-7 w-7 rounded-full object-cover border border-border"
                />
              ) : (
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-semibold">
                  {user.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
                </div>
              )}
              <div className="hidden lg:flex flex-col text-left">
                <span className="text-xs font-medium text-foreground leading-tight truncate max-w-[120px]">
                  {user.full_name}
                </span>
                <span className="text-[10px] text-muted-foreground font-mono leading-tight truncate max-w-[120px]">
                  {user.email}
                </span>
              </div>
            </div>

            {authStatus?.auth_enabled && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                onClick={() => logout()}
                title="Sign Out"
              >
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        )}
      </div>
    </header>
  );
};
