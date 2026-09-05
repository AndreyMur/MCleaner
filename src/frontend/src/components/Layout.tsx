import { NavLink, Outlet } from "react-router-dom";

const Layout = () => {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">OmniCleaner</div>
        <nav>
          <NavLink
            to="/dashboard"
            className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
          >
            <span className="nav-icon">📊</span>
            Dashboard
          </NavLink>
          <NavLink
            to="/packages"
            className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
          >
            <span className="nav-icon">📦</span>
            Packages
          </NavLink>
          <NavLink
            to="/cleaner"
            className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
          >
            <span className="nav-icon">🧹</span>
            Cleaner
          </NavLink>
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
