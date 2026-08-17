import {
  Navigate,
  Outlet,
} from "react-router";

import { useAuth } from "./useAuth";

export function RequireAdmin() {
  const {
    user,
    isLoading,
  } = useAuth();

  if (isLoading) {
    return (
      <main className="auth-loading">
        <p>
          Verificando sesión...
        </p>
      </main>
    );
  }

  if (
    !user
    || user.role !== "ADMIN"
  ) {
    return (
      <Navigate
        to="/login"
        replace
      />
    );
  }

  return <Outlet />;
}