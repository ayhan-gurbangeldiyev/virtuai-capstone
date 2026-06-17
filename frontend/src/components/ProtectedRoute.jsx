import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Loader2, ShieldX } from 'lucide-react';
import api, { API } from '@/lib/api';


export function ProtectedRoute() {
  const { t } = useTranslation();
  const { isAuthenticated, loading, signOut } = useAuth();
  const location = useLocation();
  const [authChecked, setAuthChecked] = useState(false);
  const [authorized, setAuthorized] = useState(false);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    const checkAccess = async () => {
      if (!isAuthenticated) return;
      setChecking(true);
      try {
        const res = await api.get(`${API}/auth/check`);
        if (res.data?.authorized) {
          setAuthorized(true);
        } else {
          setAuthorized(false);
        }
      } catch (err) {
        const status = err?.response?.status;
        if (status === 401) {
          // Token expire olmuş — session'ı temizle, login'e düşsün
          console.warn('Session expired, signing out...');
          await signOut();
          return;
        }
        // 403 = whitelist'te değil (yetkisiz ama session geçerli)
        setAuthorized(false);
      } finally {
        setAuthChecked(true);
        setChecking(false);
      }
    };
    checkAccess();
  }, [isAuthenticated, signOut]);

  if (loading || (isAuthenticated && !authChecked)) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Giriş yaptı ama whitelist'te değil
  if (authChecked && !authorized) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-background gap-4 p-6">
        <ShieldX className="h-16 w-16 text-red-500" />
        <h1 className="text-2xl font-bold">{t('auth.accessDenied')}</h1>
        <p className="text-muted-foreground text-center max-w-md">
          {t('auth.accessDeniedDesc')}
        </p>
        <button
          onClick={() => signOut()}
          className="mt-4 px-6 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-colors"
        >
          {t('auth.signOut')}
        </button>
      </div>
    );
  }

  return <Outlet />;
}

export function PublicRoute() {
  const { isAuthenticated, loading, signOut } = useAuth();
  const [verified, setVerified] = useState(null); // null=checking, true=valid, false=stale

  useEffect(() => {
    const verify = async () => {
      if (!isAuthenticated) {
        setVerified(false);
        return;
      }
      // Quick check: is the session actually valid?
      try {
        await api.get(`${API}/auth/check`);
        setVerified(true);
      } catch {
        // Stale session — clear it so user can login fresh
        console.warn('Stale session detected on public route, signing out...');
        await signOut();
        setVerified(false);
      }
    };
    if (!loading) verify();
  }, [isAuthenticated, loading, signOut]);

  if (loading || verified === null) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (verified) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
