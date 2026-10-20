import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, ShieldCheck, Sparkles, Terminal, ArrowRight, Loader2, KeyRound } from 'lucide-react';

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
                `Google Sign-In error (${errorInfo.type}). Ensure http://localhost:5173 is in 'Authorized JavaScript origins' in Google Cloud Console.`
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
        setLocalError('Failed to load Google Identity Services. Check your internet connection or ad-blocker settings.');
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
      setLocalError(err?.message || 'Dev login failed');
    } finally {
      setIsSubmittingDev(false);
    }
  };

  const activeError = localError || error;

  return (
    <div className="flex min-h-screen w-full flex-col justify-center bg-muted/20 py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        {/* Branding */}
        <div className="flex items-center justify-center gap-2 mb-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <span className="font-mono text-sm tracking-widest text-primary uppercase font-bold">
            Recruitment Gateway
          </span>
        </div>
        <h2 className="text-center text-2xl font-semibold tracking-tight text-foreground">
          Team Recruitment Tool
        </h2>
        <p className="mt-1 text-center text-xs text-muted-foreground">
          Single-Sign-On & Organizer Access Portal
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm sm:p-8 space-y-6">
          {/* Error Banner */}
          {activeError && (
            <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3.5 text-xs text-destructive flex items-start gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <span className="font-medium">Authentication Failed</span>
                <p className="opacity-90 leading-relaxed">{activeError}</p>
              </div>
            </div>
          )}

          {/* Section 1: Google OAuth */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Google Single Sign-On
              </span>
              <Badge variant="outline" className="text-[10px] font-mono py-0">
                OAuth 2.0
              </Badge>
            </div>

            {authStatus?.google_client_id ? (
              <div className="flex flex-col items-center justify-center pt-2">
                <div ref={googleBtnRef} className="min-h-[44px] flex items-center justify-center" />
                {isGoogleLoading && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Verifying Google token...</span>
                  </div>
                )}
                <p className="mt-2 text-[10px] text-muted-foreground text-center">
                  Origin: <code className="font-mono bg-muted/70 px-1 py-0.5 rounded border border-border/50">http://localhost:5173</code> (must be authorized in Google Console)
                </p>
              </div>
            ) : (
              <div className="rounded-lg border border-border/80 bg-muted/40 p-3 text-xs text-muted-foreground space-y-1">
                <div className="flex items-center gap-1.5 font-medium text-foreground">
                  <KeyRound className="h-3.5 w-3.5 text-primary" />
                  <span>Google Client ID Unconfigured</span>
                </div>
                <p className="text-[11px] leading-relaxed text-muted-foreground">
                  To enable Google Sign-In, add <code className="bg-background px-1 py-0.5 rounded border border-border font-mono text-[10px]">GOOGLE_CLIENT_ID</code> to your backend <code className="bg-background px-1 py-0.5 rounded border border-border font-mono text-[10px]">.env</code> file.
                </p>
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground font-mono text-[10px]">
                {authStatus?.dev_login_available ? 'Developer Quick Login' : 'Access Control'}
              </span>
            </div>
          </div>

          {/* Section 2: Dev Quick Login Fallback */}
          {authStatus?.dev_login_available ? (
            <form onSubmit={handleDevSubmit} className="space-y-4">
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs space-y-1">
                <div className="flex items-center gap-1.5 font-medium text-amber-700 dark:text-amber-400">
                  <Terminal className="h-3.5 w-3.5" />
                  <span>Development Environment Mode</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Bypass Google OAuth for local testing and demonstration. You will be authenticated with full organizer permissions.
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-foreground mb-1">
                    Organizer Name
                  </label>
                  <input
                    type="text"
                    value={devName}
                    onChange={(e) => setDevName(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                    placeholder="Lead Organizer"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-foreground mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={devEmail}
                    onChange={(e) => setDevEmail(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                    placeholder="organizer@recruitment.local"
                  />
                </div>

                <Button
                  type="submit"
                  disabled={isSubmittingDev}
                  className="w-full gap-2 text-xs font-medium"
                >
                  {isSubmittingDev ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Authenticating...</span>
                    </>
                  ) : (
                    <>
                      <span>Enter Platform as Organizer</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </>
                  )}
                </Button>
              </div>
            </form>
          ) : (
            <div className="text-center text-xs text-muted-foreground">
              Production mode active. Please authenticate via your organizational Google account.
            </div>
          )}

          {/* Footer note */}
          <div className="pt-2 text-center">
            <p className="text-[11px] text-muted-foreground flex items-center justify-center gap-1">
              <Sparkles className="h-3 w-3 text-primary" />
              <span>Single-role access model: Full recruitment platform capabilities</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
