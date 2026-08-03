import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  BookOpenText,
  Bot,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  House,
  Menu,
  Moon,
  NotebookTabs,
  Sparkles,
  Sun,
  type LucideIcon,
} from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { Dialog } from "../components";
import { RouteReveal } from "./RouteReveal";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

export interface AppShellProps {
  children?: ReactNode;
  navigation?: readonly NavItem[];
  brandName?: string;
  brandSubtitle?: string;
  footer?: ReactNode;
}

export const DEFAULT_NAVIGATION: readonly NavItem[] = [
  { to: "/app", label: "Home", icon: House, end: true },
  { to: "/notebooks", label: "Library", icon: NotebookTabs },
  { to: "/study-actions", label: "Practice", icon: Sparkles },
  { to: "/agent", label: "Ask Agentbook", icon: Bot },
  { to: "/tasks", label: "Tasks", icon: ClipboardCheck },
];

function Navigation({
  items,
  collapsed = false,
  onNavigate,
}: {
  items: readonly NavItem[];
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  return (
    <nav className="app-nav" aria-label="Primary navigation">
      <ul>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  ["app-nav__link", isActive ? "is-active" : ""]
                    .filter(Boolean)
                    .join(" ")
                }
                title={collapsed ? item.label : undefined}
                onClick={onNavigate}
              >
                <Icon size={20} strokeWidth={1.8} aria-hidden="true" />
                <span className={collapsed ? "visually-hidden" : ""}>
                  {item.label}
                </span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function AppShell({
  children,
  navigation = DEFAULT_NAVIGATION,
  brandName = "Agentbook",
  brandSubtitle = "Your private study space",
  footer,
}: AppShellProps) {
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const previousPath = useRef(location.pathname);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = stored === "dark" || (!stored && prefersDark);
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  useEffect(() => {
    setDrawerOpen(false);
    if (previousPath.current !== location.pathname) {
      mainRef.current?.focus();
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      if (sidebarRef.current) sidebarRef.current.scrollTop = 0;
      previousPath.current = location.pathname;
    }
  }, [location.pathname]);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return (
    <div
      className={[
        "app-shell",
        sidebarCollapsed ? "app-shell--collapsed" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <aside ref={sidebarRef} className="app-sidebar">
        <Link className="app-brand" to="/" aria-label="Agentbook home">
          <span className="app-brand__mark" aria-hidden="true">
            <BookOpenText size={24} />
          </span>
          <div className={sidebarCollapsed ? "visually-hidden" : "app-brand__copy"}>
            <span className="app-brand__name">{brandName}</span>
            <span className="app-brand__subtitle">{brandSubtitle}</span>
          </div>
        </Link>

        <p className={sidebarCollapsed ? "visually-hidden" : "app-nav__label"}>
          Workspace
        </p>
        <Navigation items={navigation} collapsed={sidebarCollapsed} />

        <div className="app-sidebar__footer">
          {sidebarCollapsed ? null : footer}
          <button
            type="button"
            className="app-theme-toggle"
            aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
            onClick={toggleTheme}
          >
            {dark ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
            <span className={sidebarCollapsed ? "visually-hidden" : ""}>
              {dark ? "Light mode" : "Dark mode"}
            </span>
          </button>
          <button
            type="button"
            className="sidebar-toggle"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!sidebarCollapsed}
            onClick={() => setSidebarCollapsed((current) => !current)}
          >
            {sidebarCollapsed ? (
              <ChevronRight size={19} aria-hidden="true" />
            ) : (
              <ChevronLeft size={19} aria-hidden="true" />
            )}
            <span className={sidebarCollapsed ? "visually-hidden" : ""}>
              Collapse sidebar
            </span>
          </button>
        </div>
      </aside>

      <header className="app-topbar">
        <button
          type="button"
          className="icon-button"
          aria-label="Open navigation"
          aria-expanded={drawerOpen}
          onClick={() => setDrawerOpen(true)}
        >
          <Menu size={22} aria-hidden="true" />
        </button>
        <div className="app-topbar__brand">
          <BookOpenText size={22} aria-hidden="true" />
          <span>{brandName}</span>
        </div>
        <button
          type="button"
          className="icon-button app-topbar__theme"
          aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
          onClick={toggleTheme}
        >
          {dark ? <Sun size={19} aria-hidden="true" /> : <Moon size={19} aria-hidden="true" />}
        </button>
      </header>

      <Dialog
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={brandName}
        description={brandSubtitle}
        className="app-drawer"
      >
        <Navigation items={navigation} onNavigate={() => setDrawerOpen(false)} />
        {footer ? <div className="app-drawer__footer">{footer}</div> : null}
      </Dialog>

      <main id="main-content" ref={mainRef} className="app-main" tabIndex={-1}>
        <RouteReveal key={location.key}>{children ?? <Outlet />}</RouteReveal>
      </main>
    </div>
  );
}
