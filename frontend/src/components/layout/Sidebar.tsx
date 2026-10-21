import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  PlayCircle,
  Trophy,
  SlidersHorizontal,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '@/lib/utils';
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
          'fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-200 ease-in-out md:sticky md:top-0 md:h-screen md:shrink-0 md:translate-x-0',
          isOpen ? 'translate-x-0 shadow-lg md:shadow-none' : '-translate-x-full',
          className
        )}
      >
        {/* Brand / Header (Harmonized with Login Page: ShieldCheck) */}
        <div className="flex h-16 shrink-0 items-center gap-3 border-b border-sidebar-border px-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-xs">
            <ShieldCheck className="h-5 w-5" />
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
        <div className="px-5 pt-5 pb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase shrink-0">
          Workspace Navigation
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-1 px-3 py-1 overflow-y-auto">
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

        {/* Clean Production Footer */}
        <div className="shrink-0 border-t border-sidebar-border p-4 bg-sidebar">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium text-[11px] text-muted-foreground/80">
              Team Recruitment Tool
            </span>
            <span className="font-mono text-[10px] text-muted-foreground/60">
              v1.0.0
            </span>
          </div>
        </div>
      </aside>
    </>
  );
};
