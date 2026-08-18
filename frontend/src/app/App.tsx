import { Navigate, Route, Routes } from "react-router";

import { RequireAdmin } from "../features/auth/RequireAdmin";

import { AdminLayout } from "./layouts/AdminLayout";

import { CustomerDetailPage } from "./pages/CustomerDetailPage";
import { CustomersPage } from "./pages/CustomersPage";
import { GuestSessionsPage } from "./pages/GuestSessionsPage";
import { LoginPage } from "./pages/LoginPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { RoomPage } from "./pages/RoomPage";
import { SessionsPage } from "./pages/SessionsPage";
import { StationsPage } from "./pages/StationsPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequireAdmin />}>
        <Route element={<AdminLayout />}>
          <Route path="/room" element={<RoomPage />} />

          <Route path="/customers" element={<CustomersPage />} />

          <Route
            path="/customers/:customerId"
            element={<CustomerDetailPage />}
          />

          <Route path="/stations" element={<StationsPage />} />

          <Route path="/sessions" element={<SessionsPage />} />

          <Route
            path="/guest-sessions"
            element={<GuestSessionsPage />}
          />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/room" replace />} />

      <Route
        path="*"
        element={
          <PlaceholderPage
            title="404"
            description="Página no encontrada."
          />
        }
      />
    </Routes>
  );
}