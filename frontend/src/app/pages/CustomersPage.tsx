import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
} from "react";
import { Link } from "react-router";
import {
  listCustomers,
  registerCustomer,
} from "../../features/customers/api";
import type { CustomerSummary } from "../../features/customers/types";
import { formatDuration } from "../../lib/time";
import { ApiError } from "../../lib/http";

type ActiveFilter =
  | "all"
  | "active"
  | "inactive";

function resolveIsActive(
  filter: ActiveFilter,
): boolean | undefined {
  if (filter === "active") {
    return true;
  }

  if (filter === "inactive") {
    return false;
  }

  return undefined;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(
    "es-CL",
  );
}

export function CustomersPage() {
  const [customers, setCustomers] =
    useState<CustomerSummary[]>([]);

  const [query, setQuery] =
    useState("");
  const [newUsername, setNewUsername] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const [isRegistering, setIsRegistering] =
    useState(false);

  const [registerError, setRegisterError] =
    useState<string | null>(null);

  const [registerSuccess, setRegisterSuccess] =
  useState<string | null>(null);

  const [activeFilter, setActiveFilter] =
    useState<ActiveFilter>("all");

  const [isLoading, setIsLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const loadCustomers = useCallback(
    async (
      searchQuery: string,
      filter: ActiveFilter,
    ) => {
      setIsLoading(true);
      setError(null);

      try {
        const data = await listCustomers({
          q: searchQuery,
          isActive:
            resolveIsActive(filter),
          limit: 50,
          offset: 0,
        });

        setCustomers(data);
      } catch {
        setError(
          "No fue posible cargar los clientes.",
        );
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadCustomers("", "all");
  }, [loadCustomers]);

  function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    void loadCustomers(
      query,
      activeFilter,
    );
  }

  async function handleRegisterCustomer(
  event: FormEvent<HTMLFormElement>,
) {
  event.preventDefault();

  const username =
    newUsername.trim().toLowerCase();

  const displayName =
    newDisplayName.trim();

  if (username.length < 3) {
    setRegisterError(
      "El usuario debe tener al menos 3 caracteres.",
    );
    return;
  }

  if (
    !/^[a-zA-Z0-9_.-]+$/.test(username)
  ) {
    setRegisterError(
      "El usuario sólo puede contener letras, números, _, . y -.",
    );
    return;
  }

  if (displayName.length < 2) {
    setRegisterError(
      "El nombre debe tener al menos 2 caracteres.",
    );
    return;
  }

  if (newPassword.length < 8) {
    setRegisterError(
      "La contraseña debe tener al menos 8 caracteres.",
    );
    return;
  }

  setIsRegistering(true);
  setRegisterError(null);
  setRegisterSuccess(null);

  try {
    const createdCustomer =
      await registerCustomer({
        username,
        display_name: displayName,
        password: newPassword,
      });

    setNewUsername("");
    setNewDisplayName("");
    setNewPassword("");

    setRegisterSuccess(
      `Cliente ${createdCustomer.display_name} creado correctamente.`,
    );

    await loadCustomers(
      query,
      activeFilter,
    );
  } catch (error) {
    if (
      error instanceof ApiError
      && error.status === 409
    ) {
      setRegisterError(
        "Ese nombre de usuario ya está registrado.",
      );
    } else if (
      error instanceof ApiError
      && error.status === 422
    ) {
      setRegisterError(
        "Los datos ingresados no cumplen las validaciones.",
      );
    } else {
      setRegisterError(
        "No fue posible registrar el cliente.",
      );
    }
  } finally {
    setIsRegistering(false);
  }
}

  return (
    <section className="customers-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            GCMS Admin
          </p>

          <h1>Clientes</h1>

          <p className="page-description">
            Consulta clientes registrados
            y sus saldos de tiempo.
          </p>
        </div>
      </header>
      <section className="customer-registration-section">
  <div className="section-header">
    <div>
      <h2>Nuevo cliente</h2>

      <p className="page-description">
        Registra una nueva cuenta para un cliente
        del gaming center.
      </p>
    </div>
  </div>

  <form
    className="customer-registration-form"
    onSubmit={handleRegisterCustomer}
  >
    <label className="form-field">
      <span>Usuario</span>

      <input
        type="text"
        value={newUsername}
        onChange={(event) =>
          setNewUsername(
            event.target.value,
          )
        }
        minLength={3}
        maxLength={50}
        placeholder="Ej: ivan.bozo"
        autoComplete="off"
        disabled={isRegistering}
      />
    </label>

    <label className="form-field">
      <span>Nombre</span>

      <input
        type="text"
        value={newDisplayName}
        onChange={(event) =>
          setNewDisplayName(
            event.target.value,
          )
        }
        minLength={2}
        maxLength={100}
        placeholder="Ej: Iván Bozo"
        disabled={isRegistering}
      />
    </label>

    <label className="form-field">
      <span>Contraseña</span>

      <input
        type="password"
        value={newPassword}
        onChange={(event) =>
          setNewPassword(
            event.target.value,
          )
        }
        minLength={8}
        maxLength={128}
        autoComplete="new-password"
        placeholder="Mínimo 8 caracteres"
        disabled={isRegistering}
      />
    </label>

    <button
      type="submit"
      className="primary-button"
      disabled={isRegistering}
    >
      {isRegistering
        ? "Registrando..."
        : "Registrar cliente"}
    </button>
  </form>

  {registerError && (
    <p
      className="form-error"
      role="alert"
    >
      {registerError}
    </p>
  )}

  {registerSuccess && (
    <p
      className="form-success"
      role="status"
    >
      {registerSuccess}
    </p>
  )}
</section>
      <form
        className="customer-filters"
        onSubmit={handleSubmit}
      >
        <input
          type="search"
          value={query}
          onChange={(event) =>
            setQuery(event.target.value)
          }
          placeholder="Buscar por usuario o nombre"
        />

        <select
          value={activeFilter}
          onChange={(event) =>
            setActiveFilter(
              event.target.value as ActiveFilter,
            )
          }
        >
          <option value="all">
            Todos
          </option>

          <option value="active">
            Activos
          </option>

          <option value="inactive">
            Inactivos
          </option>
        </select>

        <button
          className="primary-button"
          type="submit"
          disabled={isLoading}
        >
          Buscar
        </button>
      </form>

      {error && (
        <p
          className="form-error"
          role="alert"
        >
          {error}
        </p>
      )}

      {isLoading ? (
        <div className="content-state">
          Cargando clientes...
        </div>
      ) : customers.length === 0 ? (
        <div className="content-state">
          No se encontraron clientes.
        </div>
      ) : (
        <>
          <p className="results-count">
            Resultados cargados:
            {" "}
            {customers.length}
          </p>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Usuario</th>
                  <th>Estado</th>
                  <th>Disponible</th>
                  <th>Reservado</th>
                  <th>Registro</th>
                  <th>Acciones</th>
                </tr>
              </thead>

              <tbody>
                {customers.map(
                  (customer) => (
                    <tr key={customer.id}>
                      <td>
                        {
                          customer
                            .display_name
                        }
                      </td>

                      <td>
                        {customer.username}
                      </td>

                      <td>
                        <span
                          className={
                            customer.is_active
                              ? "status-badge active"
                              : "status-badge inactive"
                          }
                        >
                          {customer.is_active
                            ? "Activo"
                            : "Inactivo"}
                        </span>
                      </td>

                      <td>
                        {formatDuration(
                          customer
                            .available_seconds,
                        )}
                      </td>

                      <td>
                        {formatDuration(
                          customer
                            .reserved_seconds,
                        )}
                      </td>

                      <td>
                        {formatDate(
                          customer.created_at,
                        )}
                      </td>
                      <td>
                        <Link
                            className="table-link"
                            to={`/customers/${customer.id}`}
                            >
                            Ver detalle
                        </Link>
                      </td>                     
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}