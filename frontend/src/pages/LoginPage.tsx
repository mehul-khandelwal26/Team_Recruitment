import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import {
  AlertCircle,
  ShieldCheck,
  Code2,
  ChevronDown,
  ArrowRight,
  Loader2,
  SlidersHorizontal,
  Award,
  GitBranch,
} from 'lucide-react';
import { cn } from '@/lib/utils';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            error_callback?: (err: any) => void;
            auto_select?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              theme?: 'outline' | 'filled_blue' | 'filled_black';
              size?: 'large' | 'medium' | 'small';
              type?: 'standard' | 'icon';
              text?: 'signin_with' | 'signup_with' | 'continue_with';
              shape?: 'rectangular' | 'pill' | 'circle' | 'square';
              width?: number;
            }
          ) => void;
          prompt?: () => void;
        };
      };
    };
  }
}

const PIPELINE_STEPS = [
  {
    num: '01',
    name: 'Dataset',
    desc: 'CSV or JSON upload',
  },
  {
    num: '02',
    name: 'Signals',
    desc: 'GitHub, academics, resume',
  },
  {
    num: '03',
    name: 'Eligibility',
    desc: 'Set your rules',
  },
  {
    num: '04',
    name: 'Scoring',
    desc: 'Multi-criteria scoring',
  },
  {
    num: '05',
    name: 'Ranking',
    desc: 'Tie-safe Top-X',
  },
];

export const LoginPage: React.FC = () => {
  const { user, isAuthenticated, authStatus, loginWithGoogle, devLogin, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [devEmail, setDevEmail] = useState('organizer@recruitment.local');
  const [devName, setDevName] = useState('Lead Organizer');
  const [isSubmittingDev, setIsSubmittingDev] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isDevExpanded, setIsDevExpanded] = useState(false);

  const googleBtnRef = useRef<HTMLDivElement>(null);

  // If already authenticated, redirect to destination
  useEffect(() => {
    if (isAuthenticated && user) {
      const destination = (location.state as any)?.from?.pathname || '/';
      navigate(destination, { replace: true });
    }
  }, [isAuthenticated, user, navigate, location]);

  // Load Google Identity Services script if Google Client ID is configured
  useEffect(() => {
    if (!authStatus?.google_client_id) return;

    const clientId = authStatus.google_client_id;
    let script = document.getElementById('google-gis-script') as HTMLScriptElement | null;

    const handleGoogleCallback = async (response: { credential: string }) => {
      clearError();
      setLocalError(null);
      setIsGoogleLoading(true);
      try {
        await loginWithGoogle(response.credential);
      } catch (err: any) {
        setLocalError(err?.message || 'Google authentication failed');
      } finally {
        setIsGoogleLoading(false);
      }
    };

    const initializeGis = () => {
      if (window.google?.accounts?.id && googleBtnRef.current) {
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: handleGoogleCallback,
          error_callback: (errorInfo: any) => {
            console.error('Google Sign-In error:', errorInfo);
            if (errorInfo?.type && errorInfo.type !== 'popup_closed_by_user') {
              setLocalError(
                `Google Sign-In notice: ${errorInfo.type || 'Authentication failed'}`
              );
            }
          },
          auto_select: false,
        });

        googleBtnRef.current.innerHTML = '';
        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          shape: 'rectangular',
          width: 320,
        });
      }
    };

    if (!script) {
      script = document.createElement('script');
      script.id = 'google-gis-script';
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = initializeGis;
      script.onerror = () => {
        setLocalError('Failed to load Google Identity Services. Check your internet connection or browser settings.');
      };
      document.body.appendChild(script);
    } else {
      initializeGis();
    }
  }, [authStatus?.google_client_id, loginWithGoogle, clearError]);

  const handleDevSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setLocalError(null);
    setIsSubmittingDev(true);
    try {
      await devLogin(devEmail.trim() || undefined, devName.trim() || undefined);
    } catch (err: any) {
      setLocalError(err?.message || 'Sign in failed');
    } finally {
      setIsSubmittingDev(false);
    }
  };

  const activeError = localError || error;

  return (
    <div className="flex min-h-screen w-full flex-col lg:flex-row lg:h-screen lg:overflow-hidden bg-background animate-fade-in font-sans">
      {/* =========================================================================
          LEFT PANEL: Showcase & Value Proposition (~55% width on desktop)
          Hidden on mobile screens (< 1024px)
          Designed to fit comfortably on 1080p, 1440p and laptop screens without scroll
         ========================================================================= */}
      <aside
        aria-label="Platform Showcase"
        className="hidden lg:flex lg:w-[55%] h-full bg-[#0c3629] text-white flex-col justify-between p-6 xl:p-8 2xl:p-12 border-r border-emerald-950/40 select-none overflow-hidden relative"
      >
        {/* Decorative subtle ambient backdrop glow */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 -left-24 h-96 w-96 rounded-full bg-emerald-500/10 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-24 -right-24 h-96 w-96 rounded-full bg-emerald-400/10 blur-3xl"
        />

        {/* 1. Brand Row */}
        <div className="relative z-10 flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-white shadow-xs border border-white/15 backdrop-blur-xs">
            <ShieldCheck className="h-4.5 w-4.5 text-white" />
          </div>
          <span className="font-semibold text-xs tracking-widest uppercase text-white/90 font-mono">
            TEAM RECRUITMENT
          </span>
        </div>

        {/* 2. Hero Headline and Intro Description */}
        <div className="relative z-10 space-y-2 mt-2 xl:mt-3">
          <h1 className="text-2xl sm:text-3xl xl:text-[33px] 2xl:text-4xl font-bold tracking-tight text-white leading-[1.18] max-w-xl">
            Shortlist hackathon teams fairly, and explain every decision.
          </h1>
          <p className="text-xs sm:text-sm text-emerald-100/80 leading-relaxed max-w-xl">
            Upload registrations, apply your rules, score with weights you control, and get a Top-X shortlist you can defend.
          </p>
        </div>

        {/* 3. Five Equal-Sized Squarish Pipeline Step Tiles with Arrow Separators */}
        <div className="relative z-10 w-full my-2 xl:my-3">
          <div className="flex items-center justify-between w-full gap-1 sm:gap-1.5 xl:gap-2">
            {PIPELINE_STEPS.map((step, idx) => {
              const isLast = idx === PIPELINE_STEPS.length - 1;

              return (
                <React.Fragment key={step.num}>
                  {/* Pipeline Squarish Tile: Identical by default, turns crisp white on hover */}
                  <div
                    className={cn(
                      'peer group flex-1 min-w-0 rounded-xl p-2.5 xl:p-3 transition-all duration-200 cursor-default select-none',
                      'bg-white/[0.08] border border-white/15 text-white',
                      'hover:bg-white hover:border-white hover:shadow-xl hover:-translate-y-1',
                      'flex flex-col justify-between min-h-[102px] xl:min-h-[114px]'
                    )}
                  >
                    <div>
                      <span className="block text-[10px] xl:text-[11px] font-mono text-emerald-300/80 group-hover:text-emerald-700 font-semibold transition-colors duration-200 leading-none mb-1">
                        {step.num}
                      </span>
                      <div className="text-xs xl:text-sm font-semibold text-white group-hover:text-zinc-900 transition-colors duration-200 leading-tight">
                        {step.name}
                      </div>
                    </div>
                    <p className="text-[10px] xl:text-[11px] text-emerald-100/75 group-hover:text-zinc-600 leading-snug transition-colors duration-200 break-words mt-1.5">
                      {step.desc}
                    </p>
                  </div>

                  {/* Flow Arrow: Cleanly positioned between tiles with dedicated spacing, nudges forward when preceding tile is hovered */}
                  {!isLast && (
                    <div className="shrink-0 px-0.5 xl:px-1 flex items-center justify-center transition-transform duration-200 peer-hover:translate-x-1">
                      <ArrowRight className="h-3.5 w-3.5 text-emerald-300/40 transition-colors duration-200 peer-hover:text-emerald-100" />
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* 4. Compact Sample Result Card (Top-X Leaderboard) */}
        <div className="relative z-10 w-full bg-white rounded-xl p-3 xl:p-3.5 text-zinc-900 shadow-md border border-black/5">
          {/* Card Meta Header */}
          <div className="flex items-center justify-between text-[10px] mb-2 pb-1.5 border-b border-zinc-100 font-medium">
            <span className="font-mono uppercase tracking-wider text-zinc-500 font-semibold">
              SAMPLE RESULT · TOP-X LEADERBOARD
            </span>
            <span className="text-zinc-400">Explainable breakdown</span>
          </div>

          {/* Row 1: Team Nova (Eligible, 84.2) */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-mono text-zinc-400 font-medium">#1</span>
                <span className="text-xs xl:text-sm font-semibold text-zinc-900">Team Nova</span>
                <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 border border-emerald-200/80">
                  Eligible
                </span>
              </div>
              <span className="text-xs xl:text-sm font-bold font-mono text-zinc-900">84.2</span>
            </div>

            {/* Segmented breakdown bar */}
            <div className="h-2 w-full rounded-full bg-zinc-100 overflow-hidden flex">
              <div className="bg-[#144934] h-full" style={{ width: '36.2%' }} title="Academics: 30.5" />
              <div className="bg-[#22c55e] h-full" style={{ width: '33.7%' }} title="GitHub: 28.4" />
              <div className="bg-[#86efac] h-full" style={{ width: '30.1%' }} title="Resume: 25.3" />
            </div>

            {/* Breakdown Legend */}
            <div className="flex items-center gap-3 text-[10px] text-zinc-500 pt-0.5">
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-xs bg-[#144934]" />
                <span>Academics 30.5</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-xs bg-[#22c55e]" />
                <span>GitHub 28.4</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-xs bg-[#86efac]" />
                <span>Resume 25.3</span>
              </span>
            </div>
          </div>

          {/* Row 2: Team Orbit (Needs review, 79.6) */}
          <div className="mt-2 pt-1.5 border-t border-zinc-100 space-y-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-mono text-zinc-400 font-medium">#2</span>
                <span className="text-xs xl:text-sm font-semibold text-zinc-900">Team Orbit</span>
                <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700 border border-amber-200/80">
                  Needs review
                </span>
              </div>
              <span className="text-xs xl:text-sm font-bold font-mono text-zinc-900">79.6</span>
            </div>

            {/* Segmented breakdown bar */}
            <div className="h-2 w-full rounded-full bg-zinc-100 overflow-hidden flex">
              <div className="bg-[#144934] h-full" style={{ width: '35.5%' }} />
              <div className="bg-[#22c55e] h-full" style={{ width: '34.5%' }} />
              <div className="bg-[#86efac] h-full" style={{ width: '30.0%' }} />
            </div>
          </div>
        </div>

        {/* 5. Two-Column Feature Matrix (Auditable, Flexible, Tie-protected, No black-box) */}
        <div className="relative z-10 grid grid-cols-2 gap-2.5 xl:gap-3.5 pt-1">
          {/* Feature 1 */}
          <div className="flex items-start gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/10 text-emerald-300 border border-white/10">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-xs font-semibold text-white">No black-box decisions</h2>
              <p className="text-[11px] text-emerald-100/70 leading-snug mt-0.5">
                Every outcome comes with a plain-language reason.
              </p>
            </div>
          </div>

          {/* Feature 2 */}
          <div className="flex items-start gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/10 text-emerald-300 border border-white/10">
              <SlidersHorizontal className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-xs font-semibold text-white">Flexible scoring</h2>
              <p className="text-[11px] text-emerald-100/70 leading-snug mt-0.5">
                Every score adds up and can be traced back.
              </p>
            </div>
          </div>

          {/* Feature 3 */}
          <div className="flex items-start gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/10 text-emerald-300 border border-white/10">
              <Award className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-xs font-semibold text-white">Tie-protected Top-X</h2>
              <p className="text-[11px] text-emerald-100/70 leading-snug mt-0.5">
                Deterministic ranking that protects the cutoff boundary.
              </p>
            </div>
          </div>

          {/* Feature 4 */}
          <div className="flex items-start gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/10 text-emerald-300 border border-white/10">
              <GitBranch className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-xs font-semibold text-white">Versioned and auditable</h2>
              <p className="text-[11px] text-emerald-100/70 leading-snug mt-0.5">
                Immutable config versions and reason-backed overrides.
              </p>
            </div>
          </div>
        </div>
      </aside>

      {/* =========================================================================
          RIGHT PANEL: Authentication Container (~45% width on desktop, 100% mobile)
         ========================================================================= */}
      <main
        className="flex-1 w-full lg:w-[45%] flex flex-col justify-center items-center bg-background px-4 py-8 sm:px-6 lg:px-8 h-full overflow-y-auto"
      >
        {/* Mobile Header: Visible only on small/medium screens (< 1024px) */}
        <div className="lg:hidden w-full max-w-[420px] text-center mb-6">
          <div className="inline-flex items-center justify-center gap-2 mb-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <span className="font-semibold text-xs tracking-wider uppercase text-foreground/90 font-mono">
              TEAM RECRUITMENT
            </span>
          </div>
          <p className="text-xs text-muted-foreground font-medium">
            Fair, explainable hackathon shortlisting
          </p>
        </div>

        {/* Existing Functional Sign-in Card */}
        <div className="w-full max-w-[420px] rounded-xl border border-border bg-card p-6 sm:p-8 shadow-xs">
          {/* Card Heading */}
          <div className="mb-6">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
              Sign in to your recruitment workspace.
            </h1>
            <p className="mt-1 text-xs text-muted-foreground">
              Choose how you'd like to continue.
            </p>
          </div>

          {/* Error Notification Banner */}
          {activeError && (
            <div className="mb-6 rounded-lg border border-destructive/20 bg-destructive/10 p-3.5 text-xs text-destructive flex items-start gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-medium">Authentication Failed</span>
                <p className="opacity-90 leading-relaxed">{activeError}</p>
              </div>
            </div>
          )}

          {/* Option 1: Google Sign-In (Visually Prominent, drawn by Google's GIS script) */}
          <div className="space-y-3">
            {authStatus?.google_client_id ? (
              <div className="flex flex-col items-center justify-center py-1">
                <div ref={googleBtnRef} className="min-h-[44px] flex items-center justify-center w-full max-w-[320px]" />
                {isGoogleLoading && (
                  <div className="mt-2.5 flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                    <span>Verifying credentials...</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-lg border border-border/80 bg-secondary/30 p-3.5 text-center text-xs text-muted-foreground">
                Google Sign-In is not currently configured for this deployment.
              </div>
            )}
          </div>

          {/* Option 2: Developer Sign-In (Visually Secondary, Collapsible) */}
          {authStatus?.dev_login_available && (
            <>
              <div className="relative my-5">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-[11px] uppercase tracking-wider">
                  <span className="bg-card px-3 text-muted-foreground font-mono">or</span>
                </div>
              </div>

              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => setIsDevExpanded(!isDevExpanded)}
                  aria-expanded={isDevExpanded}
                  aria-controls="developer-signin-panel"
                  className="flex w-full items-center justify-between rounded-lg border border-border/60 bg-secondary/20 px-3.5 py-2.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary/40 transition-colors cursor-pointer group"
                >
                  <div className="flex items-center gap-2">
                    <Code2 className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                    <span>Developer Sign-In</span>
                  </div>
                  <ChevronDown
                    className={cn(
                      'h-4 w-4 text-muted-foreground transition-transform duration-200',
                      isDevExpanded && 'rotate-180'
                    )}
                  />
                </button>

                {isDevExpanded && (
                  <div
                    id="developer-signin-panel"
                    className="mt-3 rounded-lg border border-border/70 bg-secondary/30 p-4 space-y-3.5"
                  >
                    <form onSubmit={handleDevSubmit} className="space-y-3.5">
                      <div>
                        <label htmlFor="dev-name" className="block text-xs font-medium text-foreground mb-1">
                          Organizer Name
                        </label>
                        <input
                          id="dev-name"
                          type="text"
                          value={devName}
                          onChange={(e) => setDevName(e.target.value)}
                          className="w-full rounded-md border border-input bg-card px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-colors"
                          placeholder="Lead Organizer"
                        />
                      </div>

                      <div>
                        <label htmlFor="dev-email" className="block text-xs font-medium text-foreground mb-1">
                          Email Address
                        </label>
                        <input
                          id="dev-email"
                          type="email"
                          value={devEmail}
                          onChange={(e) => setDevEmail(e.target.value)}
                          className="w-full rounded-md border border-input bg-card px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-colors"
                          placeholder="organizer@recruitment.local"
                        />
                      </div>

                      <Button
                        type="submit"
                        disabled={isSubmittingDev}
                        className="w-full gap-2 text-xs font-medium h-9"
                      >
                        {isSubmittingDev ? (
                          <>
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            <span>Signing in...</span>
                          </>
                        ) : (
                          <>
                            <span>Enter Platform as Organizer</span>
                            <ArrowRight className="h-3.5 w-3.5" />
                          </>
                        )}
                      </Button>
                    </form>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Global Footer */}
        <footer className="mt-8 text-center">
          <p className="text-xs text-muted-foreground/80">
            Team Recruitment Tool · Recruitment Platform
          </p>
        </footer>
      </main>
    </div>
  );
};
