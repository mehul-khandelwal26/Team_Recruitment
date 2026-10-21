import React from 'react';
import { Navigate, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Loader2 } from 'lucide-react';

interface ProtectedRouteProps {
  children?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading, authStatus, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-background px-4">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="relative flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 border border-primary/20 text-primary">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
          <h2 className="text-base font-medium tracking-tight text-foreground">
            Verifying Authentication
          </h2>
          <p className="text-xs text-muted-foreground font-mono">
            Connecting to recruitment authorization gateway...
          </p>
        </div>
      </div>
    );
  }

  // If auth is not enabled by config or user is authenticated, allow entry
  if (authStatus?.auth_enabled && !isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children ? <>{children}</> : <Outlet key={user?.user_id || 'anonymous'} />;
};
