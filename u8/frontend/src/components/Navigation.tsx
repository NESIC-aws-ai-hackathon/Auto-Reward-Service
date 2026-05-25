import { NavLink, useNavigate } from 'react-router-dom';
import './Navigation.css';

export function Navigation() {
  const navigate = useNavigate();

  const handleCenterClick = (e: React.MouseEvent) => {
    e.preventDefault();
    navigate('/chat?voice=1');
  };

  return (
    <nav className="tabbar" aria-label="メインメニュー">
      <NavLink to="/chat" className={({ isActive }) => `tab${isActive ? ' active' : ''}`}>
        <span>💬</span><small>Chat</small>
      </NavLink>
      <NavLink to="/dashboard" className={({ isActive }) => `tab${isActive ? ' active' : ''}`}>
        <span>📊</span><small>家計簿</small>
      </NavLink>
      <button className="tab center" onClick={handleCenterClick} type="button">
        <img src="/assets/furemaru-avatar.png" alt="ふれまーるちゃん" />
      </button>
      <NavLink to="/diary" className={({ isActive }) => `tab${isActive ? ' active' : ''}`}>
        <span>📖</span><small>ダイアリー</small>
      </NavLink>
      <NavLink to="/recovery" className={({ isActive }) => `tab${isActive ? ' active' : ''}`}>
        <span>💞</span><small>回復</small>
      </NavLink>
    </nav>
  );
}
