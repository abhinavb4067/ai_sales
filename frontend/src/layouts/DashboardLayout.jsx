import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/agents", label: "Agents" },
  { to: "/knowledge", label: "Knowledge" },
  { to: "/leads", label: "Leads" },
  { to: "/handoff", label: "Human Handoff" },
  { to: "/api-keys", label: "API Keys" },
  { to: "/billing", label: "Billing" },
  { to: "/integrations", label: "Integrations" },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="dashboard-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">AI Sales &amp; Support</div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-user">{user?.name}</div>
          <button className="btn btn-ghost" onClick={logout}>
            Log out
          </button>
        </div>
      </aside>
      <main className="dashboard-main">
        <Outlet />
      </main>
    </div>
  );
}
