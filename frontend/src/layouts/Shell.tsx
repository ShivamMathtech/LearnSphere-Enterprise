import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  GraduationCap,
  LayoutDashboard,
  BookOpen,
  Users,
  Building2,
  Network,
  ClipboardCheck,
  CalendarDays,
  Bell,
  Award,
  BarChart3,
  Shield,
  Settings,
  UserCircle,
  LogOut,
  Moon,
  Sun,
  Menu,
  ChevronDown,
  PanelLeftClose,
  MessageSquare,
  ListChecks,
} from "lucide-react";
import { useAuth } from "../app/Auth";
import { useApi } from "../hooks/api";
import { ActionButton } from "../components/UI";
import type { Entity, Page } from "../types/domain";
const links = [
  { path: "/", label: "Overview", icon: LayoutDashboard },
  {
    path: "/courses",
    label: "Course catalog",
    icon: BookOpen,
    permission: "courses.read",
  },
  {
    path: "/learning",
    label: "My learning",
    icon: GraduationCap,
    permission: "progress.update",
  },
  {
    path: "/assessments",
    label: "Assessments",
    icon: ClipboardCheck,
    permission: "courses.read",
  },
  {
    path: "/attendance",
    label: "Live sessions",
    icon: CalendarDays,
    permission: "courses.read",
  },
  {
    path: "/community",
    label: "Community",
    icon: MessageSquare,
    permission: "courses.read",
  },
  {
    path: "/certificates",
    label: "Certificates",
    icon: Award,
    permission: "certificates.read",
  },
  { path: "/users", label: "People", icon: Users, permission: "users.read" },
  {
    path: "/academics",
    label: "Academic structure",
    icon: Network,
    permission: "academic.read",
  },
  {
    path: "/enrollments",
    label: "Enrollments",
    icon: ListChecks,
    permission: "enrollments.manage",
  },
  {
    path: "/reports",
    label: "Reports & analytics",
    icon: BarChart3,
    permission: "reports.read",
  },
  {
    path: "/roles",
    label: "Roles & permissions",
    icon: Shield,
    permission: "roles.read",
  },
  {
    path: "/institutions",
    label: "Institutions",
    icon: Building2,
    permission: "institutions.manage",
  },
  {
    path: "/audit",
    label: "Audit trail",
    icon: Shield,
    permission: "audit.read",
  },
  {
    path: "/settings",
    label: "Configuration",
    icon: Settings,
    permission: "settings.manage",
  },
];
export function SidebarLinks({ onNavigate }: { onNavigate?: () => void }) {
  const auth = useAuth();
  return (
    <nav aria-label="Main navigation">
      {links
        .filter((l) => !l.permission || auth.can(l.permission))
        .map(({ path, label, icon: Icon }) => (
          <NavLink
            end={path === "/"}
            key={path}
            to={path}
            onClick={onNavigate}
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            <Icon size={19} />
            <span>{label}</span>
          </NavLink>
        ))}
    </nav>
  );
}
export function Shell() {
  const auth = useAuth(),
    loc = useLocation();
  const [open, setOpen] = useState(false),
    [dark, setDark] = useState(localStorage.getItem("theme") === "dark");
  const institutions = useApi<Page<Entity>>(
    "/institutions?page_size=100",
    auth.can("institutions.manage"),
  );
  const notification = useApi<Page<Entity>>(
    "/notifications?unread=true&page_size=1",
    !!auth.user?.institution_id || !!auth.tenant,
  );
  const toggle = () => {
    setDark(!dark);
    document.documentElement.classList.toggle("dark", !dark);
    localStorage.setItem("theme", !dark ? "dark" : "light");
  };
  const branding = useApi<{ display_name?: string; accent?: string }>(
    "/institution-branding",
  );
  useEffect(() => {
    const accent = branding.data?.accent;
    if (accent && /^#[0-9a-fA-F]{6}$/.test(accent))
      document.documentElement.style.setProperty("--teal", accent);
    else document.documentElement.style.removeProperty("--teal");
  }, [branding.data]);
  const title =
    links.find((l) => l.path === loc.pathname)?.label || "Learning workspace";
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      {open && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={open ? "sidebar open" : "sidebar"}>
        <div className="brand">
          <GraduationCap size={31} />
          <div>
            LearnSphere<span>ENTERPRISE</span>
          </div>
          <button
            className="mobile-toggle icon-button"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <PanelLeftClose size={20} />
          </button>
        </div>
        <div className="workspace-label">
          {branding.data?.display_name ||
            (auth.user?.roles.includes("super_admin")
              ? "PLATFORM WORKSPACE"
              : "INSTITUTION WORKSPACE")}
        </div>
        {auth.can("institutions.manage") && (
          <label className="institution-select">
            Institution
            <select
              value={auth.tenant}
              onChange={(e) => auth.chooseTenant(e.target.value)}
            >
              <option value="">Platform overview</option>
              {institutions.data?.items.map((i) => (
                <option value={i.id} key={i.id}>
                  {String(i.name)}
                </option>
              ))}
            </select>
          </label>
        )}
        <SidebarLinks onNavigate={() => setOpen(false)} />
        <div className="sidebar-foot">
          <div className="workspace-card">
            <div className="status-dot" />
            <span>
              Connected learning
              <br />
              <small>Learn. Collaborate. Progress.</small>
            </span>
          </div>
          <NavLink className="nav-link" to="/profile">
            <UserCircle size={19} /> Profile & security
          </NavLink>
          <ActionButton onClick={auth.logout} className="nav-link signout">
            <LogOut size={17} /> Sign out
          </ActionButton>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-toggle"
              aria-label="Open navigation"
              onClick={() => setOpen(true)}
            >
              <Menu />
            </button>
            <span className="breadcrumb">
              Workspace <span>/</span> <strong>{title}</strong>
            </span>
          </div>
          <div className="topbar-actions">
            <span className="today">
              {new Date().toLocaleDateString([], {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
            <button
              className="icon-button"
              aria-label="Toggle color theme"
              onClick={toggle}
            >
              {dark ? <Sun size={19} /> : <Moon size={19} />}
            </button>
            <NavLink
              className="icon-button notification-icon"
              to="/notifications"
              aria-label="Notifications"
            >
              <Bell size={19} />
              {!!notification.data?.total && <span />}
            </NavLink>
            <NavLink className="profile-chip" to="/profile">
              <span className="avatar">{auth.user?.name.slice(0, 1)}</span>
              <span>
                {auth.user?.name}
                <small>{auth.user?.roles[0].replaceAll("_", " ")}</small>
              </span>
              <ChevronDown size={15} />
            </NavLink>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="footer">
          <span>LearnSphere Enterprise</span>
          <span>A little progress, every day.</span>
        </footer>
      </div>
    </div>
  );
}
