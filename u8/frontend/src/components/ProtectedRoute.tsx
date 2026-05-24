import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useApi } from '../hooks/useApi';
import { useState, useEffect } from 'react';

export function ProtectedRoute() {
  const { user, isLoading } = useAuth();
  const api = useApi();
  const location = useLocation();
  const [checkingOnboarding, setCheckingOnboarding] = useState(true);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);

  useEffect(() => {
    if (!user) {
      setCheckingOnboarding(false);
      return;
    }

    // Skip check if already on onboarding page
    if (location.pathname === '/onboarding') {
      setCheckingOnboarding(false);
      return;
    }

    // Check if user has completed onboarding (display_name is set)
    const onboarded = localStorage.getItem('fremaru_onboarded');
    if (onboarded) {
      setCheckingOnboarding(false);
      return;
    }

    // Check profile from API
    api.getSettings()
      .then((settings) => {
        if (settings.display_name) {
          localStorage.setItem('fremaru_onboarded', 'true');
          setNeedsOnboarding(false);
        } else {
          setNeedsOnboarding(true);
        }
      })
      .catch(() => {
        // If API fails, skip onboarding check (allow access)
        setNeedsOnboarding(false);
      })
      .finally(() => setCheckingOnboarding(false));
  }, [user, api, location.pathname]);

  if (isLoading || checkingOnboarding) {
    return (
      <div className="page" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100dvh' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🎀</div>
          <span style={{ color: 'var(--color-text-light)', fontSize: '0.85rem' }}>読み込み中...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (needsOnboarding && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}
