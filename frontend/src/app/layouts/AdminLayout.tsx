import {
  NavLink,
  Outlet,
} from "react-router";

import {
  useAuth,
} from "../../features/auth/useAuth";

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
  const { user, logout, } = useAuth();
  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div className="sidebar-user">
  <div>
    <span className="sidebar-user-name">
      {user?.display_name}
    </span>

    <span className="sidebar-user-role">
      Administrador
    </span>
  </div>

  <button
    className="logout-button"
    type="button"
    onClick={logout}
  >
    Cerrar sesión
  </button>
</div>
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