import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <span className="logo">V</span>
          <span>
            VoxNote <small>AI video knowledge</small>
          </span>
        </NavLink>
        <nav>
          <NavLink to="/" end>New</NavLink>
          <NavLink to="/library">Library</NavLink>
          <NavLink to="/ask">Ask</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
        <div className="user">
          <span title={user?.email}>{user?.full_name || user?.email}</span>
          <button className="btn ghost sm" onClick={logout}>Sign out</button>
        </div>
      </header>
      <main className="container">{children}</main>
      <footer className="footer">VoxNote · Turn every video into a complete learning resource.</footer>
    </div>
  );
}
