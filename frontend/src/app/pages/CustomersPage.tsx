import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
} from "react";
import { Link } from "react-router";
import { listCustomers } from "../../features/customers/api";
import type { CustomerSummary } from "../../features/customers/types";
import { formatDuration } from "../../lib/time";

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