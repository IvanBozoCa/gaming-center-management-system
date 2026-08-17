import {
  useState,
  type FormEvent,
} from "react";
import { useNavigate,Navigate, } from "react-router";

import {  useAuth, } from "../../features/auth/useAuth";

import { login } from "../../features/auth/api";

import { ApiError } from "../../lib/http";

export function LoginPage() {
  const navigate = useNavigate();
  const { user, establishSession, } = useAuth();

  const [username, setUsername] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [isSubmitting, setIsSubmitting] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);
  
  if (user?.role === "ADMIN") {
  return (
    <Navigate
      to="/customers"
      replace
    />
  );
}

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const normalizedUsername =
      username.trim();

    if (
      !normalizedUsername
      || !password
    ) {
      setError(
        "Ingresa usuario y contraseña.",
      );

      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const response = await login({
        username: normalizedUsername,
        password,
      });

      await establishSession( response.access_token, );

      navigate(
        "/customers",
        {
          replace: true,
        },
      );
    } catch (error) {
      if (
        error instanceof ApiError
        && error.status === 401
      ) {
        setError(
          "Usuario o contraseña incorrectos.",
        );
      } else {
        setError(
          "No fue posible iniciar sesión.",
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div>
          <p className="eyebrow">
            GCMS Admin
          </p>

          <h1>
            Iniciar sesión
          </h1>

          <p className="login-description">
            Accede al panel administrativo
            del gaming center.
          </p>
        </div>

        <form
          className="login-form"
          onSubmit={handleSubmit}
        >
          <label className="form-field">
            <span>
              Usuario
            </span>

            <input
              type="text"
              value={username}
              onChange={(event) =>
                setUsername(
                  event.target.value,
                )
              }
              autoComplete="username"
              disabled={isSubmitting}
            />
          </label>

          <label className="form-field">
            <span>
              Contraseña
            </span>

            <input
              type="password"
              value={password}
              onChange={(event) =>
                setPassword(
                  event.target.value,
                )
              }
              autoComplete="current-password"
              disabled={isSubmitting}
            />
          </label>

          {error && (
            <p
              className="form-error"
              role="alert"
            >
              {error}
            </p>
          )}

          <button
            className="primary-button"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? "Ingresando..."
              : "Ingresar"}
          </button>
        </form>
      </section>
    </main>
  );
}