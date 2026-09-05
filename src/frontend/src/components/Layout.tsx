import { NavLink, Outlet, useLocation } from "react-router-dom";
import FullscreenButton from "./FullscreenButton";
import JournalPanel from "./JournalPanel";
import ThemeToggle from "./ThemeToggle";

const NAV_ITEMS = [
  { to: "/dashboard", icon: "📊", label: "Dashboard" },
  { to: "/packages", icon: "📦", label: "Packages" },
  { to: "/cleaner", icon: "🧹", label: "Cleaner" },
];

const Layout = () => {
  const location = useLocation();

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-body">
          <div className="sidebar-logo">
            <span className="sidebar-logo-mark" aria-hidden="true">
              🧹
            </span>
            <span className="sidebar-brand">MCleaner</span>
          </div>
          <nav className="sidebar-nav">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  isActive ? "nav-item active" : "nav-item"
                }
              >
                <span className="nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="nav-label">{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="sidebar-footer">
          <ThemeToggle />
          <FullscreenButton />
        </div>
      </aside>
      <div className="app-content">
        <main className="main-content">
          <div className="page-view" key={location.pathname}>
            <Outlet />
          </div>
        </main>
        <JournalPanel />
      </div>
    </div>
  );
};

export default Layout;
