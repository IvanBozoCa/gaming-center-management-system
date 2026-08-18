import { useCallback, useEffect, useState } from "react";

import {
  finishGuestSession,
  listActiveGuestSessions,
  listGuestSessionHistory,
} from "../../features/guest-sessions/api";

import type {
  ActiveGuestSession,
  FinishedGuestSession,
  GuestSessionTimeState,
} from "../../features/guest-sessions/types";

import { listStations } from "../../features/stations/api";

import type { Station } from "../../features/stations/types";

import { ApiError } from "../../lib/http";

import { formatDuration } from "../../lib/time";

const GUEST_HISTORY_PAGE_SIZE = 20;

const timeStateLabels: Record<GuestSessionTimeState, string> = {
  RUNNING: "En curso",
  EXHAUSTED: "Sin tiempo · activa",
};

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("es-CL");
}

function getFinishErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "No fue posible finalizar la sesión de invitado.";
  }

  if (error.status === 404) {
    return "La sesión de invitado ya no existe.";
  }

  if (
    error.status === 409 &&
    error.message === "Guest session is already finished"
  ) {
    return "La sesión ya fue finalizada.";
  }

  if (
    error.status === 409 &&
    error.message === "Guest session station not found"
  ) {
    return "La estación asociada a la sesión ya no existe.";
  }

  if (error.status === 409) {
    return "No fue posible finalizar la sesión por un conflicto de estado.";
  }

  return "No fue posible finalizar la sesión de invitado.";
}

export function GuestSessionsPage() {
  /*
   * Sesiones activas
   */

  const [sessions, setSessions] = useState<ActiveGuestSession[]>([]);

  const [isLoading, setIsLoading] = useState(true);

  const [isRefreshing, setIsRefreshing] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [feedback, setFeedback] = useState<string | null>(null);

  const [finishingSessionId, setFinishingSessionId] = useState<string | null>(
    null,
  );

  const [finishError, setFinishError] = useState<string | null>(null);

  /*
   * Historial
   */

  const [history, setHistory] = useState<FinishedGuestSession[]>([]);

  const [historyStations, setHistoryStations] = useState<Station[]>([]);

  const [historyStationId, setHistoryStationId] = useState("");

  const [historyOffset, setHistoryOffset] = useState(0);

  const [historyHasNext, setHistoryHasNext] = useState(false);

  const [isHistoryLoading, setIsHistoryLoading] = useState(true);

  const [historyError, setHistoryError] = useState<string | null>(null);

  /*
   * Sesiones activas
   */

  const loadSessions = useCallback(
    async (showFullLoading = true): Promise<boolean> => {
      if (showFullLoading) {
        setIsLoading(true);
      }

      setError(null);

      try {
        const data = await listActiveGuestSessions();

        setSessions(data);

        return true;
      } catch {
        setError("No fue posible cargar las sesiones GUEST activas.");

        return false;
      } finally {
        if (showFullLoading) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  /*
   * Estaciones para filtros de historial
   */

  const loadHistoryStations = useCallback(async (): Promise<boolean> => {
    try {
      const data = await listStations();

      setHistoryStations(data);

      return true;
    } catch {
      return false;
    }
  }, []);

  /*
   * Historial GUEST
   */

  const loadHistory = useCallback(
    async (offset: number, stationId: string): Promise<boolean> => {
      setIsHistoryLoading(true);

      setHistoryError(null);

      try {
        const data = await listGuestSessionHistory({
          stationId: stationId || undefined,

          limit: GUEST_HISTORY_PAGE_SIZE + 1,

          offset,
        });

        setHistory(data.slice(0, GUEST_HISTORY_PAGE_SIZE));

        setHistoryHasNext(data.length > GUEST_HISTORY_PAGE_SIZE);

        return true;
      } catch {
        setHistoryError("No fue posible cargar el historial GUEST.");

        return false;
      } finally {
        setIsHistoryLoading(false);
      }
    },
    [],
  );

  /*
   * Carga inicial
   */

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    void loadHistoryStations();
  }, [loadHistoryStations]);

  useEffect(() => {
    void loadHistory(historyOffset, historyStationId);
  }, [loadHistory, historyOffset, historyStationId]);

  /*
   * Actualizar sesiones activas
   */

  async function handleRefresh() {
    setIsRefreshing(true);

    setFeedback(null);

    const success = await loadSessions(false);

    if (success) {
      setFeedback("Sesiones GUEST actualizadas.");
    }

    setIsRefreshing(false);
  }

  /*
   * Finalizar sesión GUEST
   */

  async function handleFinishSession(session: ActiveGuestSession) {
    const confirmed = window.confirm(
      `¿Finalizar la sesión de invitado en ${session.station_code}?`,
    );

    if (!confirmed) {
      return;
    }

    setFinishingSessionId(session.session_id);

    setFinishError(null);

    setFeedback(null);

    try {
      const finishedSession = await finishGuestSession(session.session_id);

      setSessions((currentSessions) =>
        currentSessions.filter(
          (currentSession) => currentSession.session_id !== session.session_id,
        ),
      );

      const historyUpdated = await loadHistory(historyOffset, historyStationId);

      if (!historyUpdated) {
        setFeedback(
          "La sesión fue finalizada, pero no fue posible actualizar el historial.",
        );
      } else {
        setFeedback(
          `${session.station_code} finalizada: ${formatDuration(
            finishedSession.consumed_seconds,
          )} consumidos y ${formatDuration(
            finishedSession.unused_seconds,
          )} no utilizados.`,
        );
      }
    } catch (finishSessionError) {
      setFinishError(getFinishErrorMessage(finishSessionError));
    } finally {
      setFinishingSessionId(null);
    }
  }

  return (
    <section className="sessions-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">GCMS Admin</p>

          <h1>Sesiones de invitados</h1>

          <p className="page-description">
            Supervisa las sesiones temporales de usuarios sin cuenta. Las nuevas
            ventas GUEST se realizan desde Sala seleccionando una estación
            disponible y una tarifa activa.
          </p>
        </div>
      </header>

      {/* SESIONES GUEST ACTIVAS */}

      <section className="active-sessions-section">
        <div className="section-header">
          <div>
            <h2>Sesiones GUEST activas</h2>

            <p className="page-description">
              El tiempo mostrado se calcula con el reloj del servidor.
            </p>
          </div>

          <button
            type="button"
            className="secondary-button"
            disabled={isRefreshing}
            onClick={() => void handleRefresh()}
          >
            {isRefreshing ? "Actualizando..." : "Actualizar"}
          </button>
        </div>

        {feedback && (
          <p className="form-success" role="status">
            {feedback}
          </p>
        )}

        {finishError && (
          <p className="form-error" role="alert">
            {finishError}
          </p>
        )}

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        {isLoading ? (
          <div className="content-state">Cargando sesiones...</div>
        ) : sessions.length === 0 ? (
          <div className="content-state">No hay sesiones GUEST activas.</div>
        ) : (
          <>
            <p className="results-count">Sesiones activas: {sessions.length}</p>

            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Estación</th>

                    <th>Estado</th>

                    <th>Autorizado</th>

                    <th>Transcurrido</th>

                    <th>Restante</th>

                    <th>Inicio</th>

                    <th>Acciones</th>
                  </tr>
                </thead>

                <tbody>
                  {sessions.map((session) => (
                    <tr key={session.session_id}>
                      <td>
                        <strong>{session.station_code}</strong>

                        <div className="table-secondary-text">Invitado</div>
                      </td>

                      <td>
                        <span
                          className={
                            "session-time-state " +
                            session.time_state.toLowerCase()
                          }
                        >
                          {timeStateLabels[session.time_state]}
                        </span>
                      </td>

                      <td>{formatDuration(session.authorized_seconds)}</td>

                      <td>{formatDuration(session.elapsed_seconds)}</td>

                      <td>
                        <strong>
                          {formatDuration(session.remaining_seconds)}
                        </strong>
                      </td>

                      <td>{formatDateTime(session.started_at)}</td>

                      <td>
                        <button
                          type="button"
                          className="danger-button"
                          disabled={finishingSessionId === session.session_id}
                          onClick={() => void handleFinishSession(session)}
                        >
                          {finishingSessionId === session.session_id
                            ? "Finalizando..."
                            : "Finalizar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {/* HISTORIAL GUEST */}

      <section className="session-history-section">
        <div className="section-header">
          <div>
            <h2>Historial GUEST</h2>

            <p className="page-description">
              Sesiones de invitados finalizadas.
            </p>
          </div>
        </div>

        <div className="session-history-filters guest-history-filters">
          <label className="form-field">
            <span>Estación</span>

            <select
              value={historyStationId}
              onChange={(event) => {
                setHistoryStationId(event.target.value);

                setHistoryOffset(0);
              }}
            >
              <option value="">Todas las estaciones</option>

              {historyStations.map((station) => (
                <option key={station.id} value={station.id}>
                  {station.code}
                </option>
              ))}
            </select>
          </label>
        </div>

        {historyError && (
          <p className="form-error" role="alert">
            {historyError}
          </p>
        )}

        {isHistoryLoading ? (
          <div className="content-state">Cargando historial...</div>
        ) : history.length === 0 ? (
          <div className="content-state">
            No hay sesiones GUEST finalizadas para estos filtros.
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Estación</th>

                    <th>Autorizado</th>

                    <th>Consumido</th>

                    <th>No utilizado</th>

                    <th>Inicio</th>

                    <th>Fin</th>
                  </tr>
                </thead>

                <tbody>
                  {history.map((session) => (
                    <tr key={session.session_id}>
                      <td>
                        <strong>{session.station_code}</strong>

                        <div className="table-secondary-text">Invitado</div>
                      </td>

                      <td>{formatDuration(session.authorized_seconds)}</td>

                      <td>{formatDuration(session.consumed_seconds)}</td>

                      <td>{formatDuration(session.unused_seconds)}</td>

                      <td>{formatDateTime(session.started_at)}</td>

                      <td>{formatDateTime(session.ended_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination-controls">
              <button
                type="button"
                className="secondary-button"
                disabled={historyOffset === 0}
                onClick={() =>
                  setHistoryOffset((current) =>
                    Math.max(0, current - GUEST_HISTORY_PAGE_SIZE),
                  )
                }
              >
                Anterior
              </button>

              <span>
                Página {Math.floor(historyOffset / GUEST_HISTORY_PAGE_SIZE) + 1}
              </span>

              <button
                type="button"
                className="secondary-button"
                disabled={!historyHasNext}
                onClick={() =>
                  setHistoryOffset(
                    (current) => current + GUEST_HISTORY_PAGE_SIZE,
                  )
                }
              >
                Siguiente
              </button>
            </div>
          </>
        )}
      </section>
    </section>
  );
}
