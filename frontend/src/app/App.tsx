import { Navigate, Route, Routes } from "react-router";

import { RequireAdmin } from "../features/auth/RequireAdmin";
import { AdminLayout } from "./layouts/AdminLayout";
import { LoginPage } from "./pages/LoginPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequireAdmin />}>
        <Route element={<AdminLayout />}>
          <Route
            path="/customers"
            element={
              <PlaceholderPage
                title="Clientes"
                description={"Gestión de clientes, " + "wallet e historial."}
              />
            }
          />

          <Route
            path="/stations"
            element={
              <PlaceholderPage
                title="Estaciones"
                description={
                  "Administración de los " + "equipos del gaming center."
                }
              />
            }
          />

          <Route
            path="/sessions"
            element={
              <PlaceholderPage
                title="Sesiones"
                description={"Sesiones de clientes " + "registrados."}
              />
            }
          />

          <Route
            path="/guest-sessions"
            element={
              <PlaceholderPage
                title="Invitados"
                description="Sesiones temporales GUEST."
              />
            }
          />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/customers" replace />} />

      <Route
        path="*"
        element={
          <PlaceholderPage title="404" description="Página no encontrada." />
        }
      />
    </Routes>
  );
}
