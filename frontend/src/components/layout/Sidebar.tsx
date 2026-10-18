import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  PlayCircle,
  Trophy,
  SlidersHorizontal,
  GraduationCap,
  Sparkles,
  Server,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import type { NavItem } from '@/types';

export const navigationItems: NavItem[] = [
  {
    title: 'Dashboard',
    href: '/',
    icon: LayoutDashboard,
    description: 'System overview & recent runs',
  },
  {
    title: 'New Evaluation',
    href: '/evaluate',
    icon: PlayCircle,
    description: 'Multi-step shortlisting pipeline',
  },
  {
    title: 'Results',
    href: '/results',
    icon: Trophy,
    description: 'Ranked shortlists & explainability',
  },
  {
    title: 'Configurations',
    href: '/configurations',
    icon: SlidersHorizontal,
    description: 'Eligibility rules & scoring presets',
  },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen = false,
  onClose,
  className,
}) => {
  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-xs md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-200 ease-in-out md:static md:translate-x-0',
          isOpen ? 'translate-x-0 shadow-lg md:shadow-none' : '-translate-x-full',
          className
        )}
      >
        {/* Brand / Header */}
        <div className="flex h-16 shrink-0 items-center gap-3 border-b border-sidebar-border px-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-xs">
            <GraduationCap className="h-5 w-5" />
          </div>
          <div className="flex flex-col min-w-0">
            <span className="font-semibold text-sm tracking-tight text-foreground truncate">
              Team Recruitment
            </span>
            <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              Automation Tool
            </span>
          </div>
        </div>

        {/* Section Title */}
        <div className="px-5 pt-5 pb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
          Workspace Navigation
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-1 px-3 py-1">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.href}
                to={item.href}
                onClick={onClose}
                end={item.href === '/'}
                className={({ isActive }) =>
                  cn(
                    'group flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-xs'
                      : 'text-sidebar-foreground hover:bg-secondary/70 hover:text-foreground'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn(
                        'h-4 w-4 shrink-0 transition-colors',
                        isActive
                          ? 'text-primary-foreground'
                          : 'text-muted-foreground group-hover:text-foreground'
                      )}
                    />
                    <div className="flex flex-1 flex-col truncate">
                      <span className="truncate leading-tight">{item.title}</span>
                      <span
                        className={cn(
                          'text-[11px] font-normal truncate mt-0.5',
                          isActive ? 'text-primary-foreground/80' : 'text-muted-foreground'
                        )}
                      >
                        {item.description}
                      </span>
                    </div>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Footer / System Context */}
        <div className="border-t border-sidebar-border p-4 space-y-2 bg-sidebar">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5 font-medium">
              <Server className="h-3.5 w-3.5 text-emerald-600" />
              API Ready
            </span>
            <Badge variant="forest" className="text-[10px] py-0 px-1.5 font-mono">
              FastAPI v0.1.0
            </Badge>
          </div>
          <div className="rounded border border-border/60 bg-card/60 p-2 text-[11px] text-muted-foreground leading-normal">
            <div className="flex items-center gap-1.5 font-medium text-foreground mb-0.5">
              <Sparkles className="h-3 w-3 text-forest-700" />
              Editorial Enterprise
            </div>
            Deterministic 3-state eligibility & weighted scoring shortlist engine.
          </div>
        </div>
      </aside>
    </>
  );
};
