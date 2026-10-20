import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { AlertCircle, ShieldCheck, Code2, ChevronDown, ArrowRight, Loader2 } from 'lucide-react';
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
    <div className="flex min-h-screen w-full flex-col justify-center items-center bg-background px-4 py-12 sm:px-6 lg:px-8">
      {/* Branding and Page Heading */}
      <div className="w-full max-w-[420px] text-center mb-6">
        <div className="inline-flex items-center justify-center gap-2.5 mb-3.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <span className="font-semibold text-xs tracking-wider uppercase text-foreground/90 font-mono">
            TEAM RECRUITMENT
          </span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-foreground">
          Welcome back.
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Sign in to access your recruitment workspace.
        </p>
      </div>

      {/* Login Card */}
      <div className="w-full max-w-[420px] rounded-xl border border-border bg-card p-6 sm:p-8 shadow-xs">
        {/* Card Heading */}
        <div className="mb-6">
          <h2 className="text-base font-semibold text-foreground">
            Welcome back
          </h2>
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

        {/* Option 1: Google Sign-In (Visually Prominent) */}
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

      {/* Footer */}
      <footer className="mt-8 text-center">
        <p className="text-xs text-muted-foreground/80">
          Team Recruitment Tool · Recruitment Platform
        </p>
      </footer>
    </div>
  );
};
