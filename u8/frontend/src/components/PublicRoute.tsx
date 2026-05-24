import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function PublicRoute() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <div className="page" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>読み込み中...</div>;
  }

  if (user) {
    return <Navigate to="/chat" replace />;
  }

  return <Outlet />;
}
