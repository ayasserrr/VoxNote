import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { BookOpenCheck, Brain, GraduationCap, LayoutDashboard, Library, LogOut, Menu, MessageCircleQuestion, PlusCircle, Settings, X } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/new", label: "New", icon: PlusCircle },
  { to: "/learn", label: "Learning Hub", icon: GraduationCap },
  { to: "/review", label: "Review", icon: Brain },
  { to: "/library", label: "Library", icon: Library },
  { to: "/ask", label: "Ask", icon: MessageCircleQuestion },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [due, setDue] = useState(0);
  const loc = useLocation();
  useEffect(() => {
    api.review().then((q) => setDue(q.due)).catch(() => undefined);
  }, [loc.pathname]);
  useEffect(() => {
    setOpen(false);
  }, [loc.pathname]);
  const initials = (user?.full_name || user?.email || "?").slice(0, 1).toUpperCase();

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <NavLink to="/" className="brand">
          <span className="logo"><BookOpenCheck size={20} /></span>
          <span>
            VoxNote <small>Learning hub</small>
          </span>
        </NavLink>
        <nav>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon size={18} />
              {label}
              {to === "/review" && due > 0 && <span className="nav-badge">{due}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="avatar">{initials}</div>
          <div className="who">
            <strong>{user?.full_name || "Learner"}</strong>
            <small>{user?.email}</small>
          </div>
          <button className="icon-btn" onClick={logout} title="Sign out">
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <div className="main">
        <header className="mobilebar">
          <button className="icon-btn" onClick={() => setOpen(!open)} aria-label="Menu">
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="brand-mini"><BookOpenCheck size={18} /> VoxNote</span>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
