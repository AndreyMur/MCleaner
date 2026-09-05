import { NavLink, Outlet } from "react-router-dom";
import JournalPanel from "./JournalPanel";
import ThemeToggle from "./ThemeToggle";

const NAV_ITEMS = [
  { to: "/dashboard", icon: "📊", label: "Dashboard" },
  { to: "/packages", icon: "📦", label: "Packages" },
  { to: "/cleaner", icon: "🧹", label: "Cleaner" },
];

const Layout = () => {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-body">
          <div className="sidebar-logo">
            <span className="sidebar-logo-mark" aria-hidden="true">
              🧹
            </span>
            <span className="sidebar-brand">OmniCleaner</span>
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
        </div>
      </aside>
      <div className="app-content">
        <main className="main-content">
          <Outlet />
        </main>
        <JournalPanel />
      </div>
    </div>
  );
};

export default Layout;
