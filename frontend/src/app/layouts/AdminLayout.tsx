import {
  NavLink,
  Outlet,
} from "react-router";

const navigationItems = [
  {
    to: "/customers",
    label: "Clientes",
  },
  {
    to: "/stations",
    label: "Estaciones",
  },
  {
    to: "/sessions",
    label: "Sesiones",
  },
  {
    to: "/guest-sessions",
    label: "Invitados",
  },
];

export function AdminLayout() {
  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">
            GCMS
          </p>

          <h2>Gaming Center</h2>
        </div>

        <nav className="sidebar-nav">
          {navigationItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive
                  ? "nav-link active"
                  : "nav-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}