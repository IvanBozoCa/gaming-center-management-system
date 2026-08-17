import {
  useCallback,
  useEffect,
  useState,
} from "react";

import { listActiveRegisteredSessions } from "../../features/sessions/api";
import type {
  ActiveRegisteredSession,
  SessionTimeState,
} from "../../features/sessions/types";
import { formatDuration } from "../../lib/time";

const timeStateLabels: Record<SessionTimeState, string> = {
  RUNNING: "En curso",
  EXHAUSTED: "Sin tiempo · activa",
};

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("es-CL");
}

export function SessionsPage() {
  const [sessions, setSessions] =
    useState<ActiveRegisteredSession[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const loadSessions = useCallback(
    async (showFullLoading = true): Promise<boolean> => {
      if (showFullLoading) {
        setIsLoading(true);
      }

      setError(null);

      try {
        const data = await listActiveRegisteredSessions();
        setSessions(data);

        return true;
      } catch {
        setError(
          "No fue posible cargar las sesiones activas.",
        );

        return false;
      } finally {
        if (showFullLoading) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  async function handleRefresh() {
    setIsRefreshing(true);
    setFeedback(null);

    const success = await loadSessions(false);

    if (success) {
      setFeedback("Sesiones activas actualizadas.");
    }

    setIsRefreshing(false);
  }

  return (
    <section className="sessions-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">GCMS Admin</p>

          <h1>Sesiones</h1>

          <p className="page-description">
            Supervisa las sesiones activas de clientes registrados.
          </p>
        </div>
      </header>

      <section className="active-sessions-section">
        <div className="section-header">
          <div>
            <h2>Sesiones activas</h2>

            <p className="page-description">
              Estado actual informado por el backend.
            </p>
          </div>

          <button
            type="button"
            className="secondary-button"
            onClick={() => void handleRefresh()}
            disabled={isRefreshing}
          >
            {isRefreshing ? "Actualizando..." : "Actualizar"}
          </button>
        </div>

        {feedback && (
          <p className="form-success" role="status">
            {feedback}
          </p>
        )}

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        {isLoading ? (
          <div className="content-state">
            Cargando sesiones activas...
          </div>
        ) : sessions.length === 0 ? (
          <div className="content-state">
            No hay sesiones REGISTERED activas.
          </div>
        ) : (
          <>
            <p className="results-count">
              Sesiones activas: {sessions.length}
            </p>

            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Estación</th>
                    <th>Cliente</th>
                    <th>Estado</th>
                    <th>Autorizado</th>
                    <th>Transcurrido</th>
                    <th>Restante</th>
                    <th>Inicio</th>
                  </tr>
                </thead>

                <tbody>
                  {sessions.map((session) => (
                    <tr key={session.session_id}>
                      <td>
                        <strong>
                          {session.station_code}
                        </strong>
                      </td>

                      <td>
                        <strong>
                          {session.customer_display_name}
                        </strong>

                        <div className="table-secondary-text">
                          @{session.customer_username}
                        </div>
                      </td>

                      <td>
                        <span
                          className={
                            `session-time-state `
                            + session.time_state.toLowerCase()
                          }
                        >
                          {timeStateLabels[session.time_state]}
                        </span>
                      </td>

                      <td>
                        {formatDuration(
                          session.authorized_seconds,
                        )}
                      </td>

                      <td>
                        {formatDuration(
                          session.elapsed_seconds,
                        )}
                      </td>

                      <td>
                        <strong>
                          {formatDuration(
                            session.remaining_seconds,
                          )}
                        </strong>
                      </td>

                      <td>
                        {formatDateTime(session.started_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </section>
  );
}