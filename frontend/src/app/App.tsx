import { Navigate, Route, Routes } from "react-router";
import { CustomersPage } from "./pages/CustomersPage";
import { RequireAdmin } from "../features/auth/RequireAdmin";
import { AdminLayout } from "./layouts/AdminLayout";
import { LoginPage } from "./pages/LoginPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { StationsPage } from "./pages/StationsPage";
import { SessionsPage } from "./pages/SessionsPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequireAdmin />}>
        <Route element={<AdminLayout />}>
          <Route path="/customers" element={<CustomersPage />} />

          <Route path="/stations" element={<StationsPage />} />

          <Route path="/sessions" element={<SessionsPage />} />

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
