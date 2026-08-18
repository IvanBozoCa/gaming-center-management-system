import { useCallback, useEffect, useState } from "react";

import {
  extendRegisteredSession,
  finishRegisteredSession,
  listActiveRegisteredSessions,
  listRegisteredSessionHistory,
} from "../../features/sessions/api";

import type {
  ActiveRegisteredSession,
  FinishedRegisteredSession,
  SessionTimeState,
} from "../../features/sessions/types";

import { listCustomers } from "../../features/customers/api";

import type { CustomerSummary } from "../../features/customers/types";

import { listStations } from "../../features/stations/api";

import type { Station } from "../../features/stations/types";

import { formatDuration } from "../../lib/time";

import { ApiError } from "../../lib/http";

const HISTORY_PAGE_SIZE = 20;

const timeStateLabels: Record<SessionTimeState, string> = {
  RUNNING: "En curso",
  EXHAUSTED: "Sin tiempo · activa",
};

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("es-CL");
}

function getExtensionErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "No fue posible extender la sesión.";
  }

  if (error.status === 404) {
    return "La sesión ya no existe.";
  }

  if (error.status === 422) {
    return "El tiempo adicional debe ser mayor que cero.";
  }

  if (error.status === 409 && error.message === "Insufficient time balance") {
    return "El cliente no tiene saldo suficiente para esa extensión.";
  }

  if (
    error.status === 409 &&
    error.message === "Usage session is already finished"
  ) {
    return "La sesión ya fue finalizada.";
  }

  if (error.status === 409) {
    return "No fue posible extender la sesión por un conflicto de estado.";
  }

  return "No fue posible extender la sesión.";
}

function getFinishErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "No fue posible finalizar la sesión.";
  }

  if (error.status === 404) {
    return "La sesión ya no existe.";
  }

  if (
    error.status === 409 &&
    error.message === "Usage session is already finished"
  ) {
    return "La sesión ya fue finalizada.";
  }

  if (
    error.status === 409 &&
    error.message === "Session reservation is inconsistent"
  ) {
    return "La reserva de tiempo de la sesión es inconsistente.";
  }

  if (error.status === 409) {
    return "No fue posible finalizar la sesión por un conflicto de estado.";
  }

  return "No fue posible finalizar la sesión.";
}

export function SessionsPage() {
  /*
   * Sesiones activas
   */

  const [sessions, setSessions] = useState<ActiveRegisteredSession[]>([]);

  const [isLoading, setIsLoading] = useState(true);

  const [isRefreshing, setIsRefreshing] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [feedback, setFeedback] = useState<string | null>(null);

  /*
   * Acciones sobre sesiones activas
   */

  const [extensionMinutes, setExtensionMinutes] = useState<
    Record<string, string>
  >({});

  const [sessionActionId, setSessionActionId] = useState<string | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);

  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  /*
   * Historial
   */

  const [history, setHistory] = useState<FinishedRegisteredSession[]>([]);

  const [historyCustomers, setHistoryCustomers] = useState<CustomerSummary[]>(
    [],
  );

  const [historyStations, setHistoryStations] = useState<Station[]>([]);

  const [historyCustomerId, setHistoryCustomerId] = useState("");

  const [historyStationId, setHistoryStationId] = useState("");

  const [historyOffset, setHistoryOffset] = useState(0);

  const [isHistoryLoading, setIsHistoryLoading] = useState(true);

  const [historyError, setHistoryError] = useState<string | null>(null);

  /*
   * Carga de sesiones activas
   */

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
        setError("No fue posible cargar las sesiones activas.");

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
   * Opciones para filtros del historial
   */

  const loadHistoryOptions = useCallback(async (): Promise<boolean> => {
    try {
      const [customerData, stationData] = await Promise.all([
        listCustomers({
          limit: 100,
        }),

        listStations(),
      ]);

      setHistoryCustomers(customerData);

      setHistoryStations(stationData);

      return true;
    } catch {
      return false;
    }
  }, []);

  /*
   * Historial de sesiones REGISTERED
   */

  const loadHistory = useCallback(
    async (
      offset: number,
      customerId: string,
      stationId: string,
    ): Promise<boolean> => {
      setIsHistoryLoading(true);

      setHistoryError(null);

      try {
        const data = await listRegisteredSessionHistory({
          customerId: customerId || undefined,

          stationId: stationId || undefined,

          limit: HISTORY_PAGE_SIZE,

          offset,
        });

        setHistory(data);

        return true;
      } catch {
        setHistoryError("No fue posible cargar el historial de sesiones.");

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
    void loadHistoryOptions();
  }, [loadHistoryOptions]);

  useEffect(() => {
    void loadHistory(historyOffset, historyCustomerId, historyStationId);
  }, [loadHistory, historyOffset, historyCustomerId, historyStationId]);

  /*
   * Actualizar sesiones activas
   */

  async function handleRefresh() {
    setIsRefreshing(true);

    setFeedback(null);

    const success = await loadSessions(false);

    if (success) {
      setFeedback("Sesiones activas actualizadas.");
    }

    setIsRefreshing(false);
  }

  /*
   * Extender una sesión
   */

  async function handleExtendSession(session: ActiveRegisteredSession) {
    const rawMinutes = extensionMinutes[session.session_id] ?? "";

    const minutes = Number(rawMinutes);

    if (!Number.isFinite(minutes) || minutes <= 0) {
      setActionError("Ingresa una cantidad de minutos mayor que cero.");

      return;
    }

    const additionalSeconds = Math.floor(minutes * 60);

    setSessionActionId(session.session_id);

    setActionError(null);

    setActionSuccess(null);

    try {
      const extendedSession = await extendRegisteredSession(
        session.session_id,
        {
          additional_seconds: additionalSeconds,
        },
      );

      setExtensionMinutes((current) => ({
        ...current,

        [session.session_id]: "",
      }));

      const sessionsUpdated = await loadSessions(false);

      if (sessionsUpdated) {
        setActionSuccess(
          `${session.station_code} recibió ${formatDuration(
            extendedSession.additional_seconds,
          )} adicionales.`,
        );
      } else {
        setActionSuccess(
          "El tiempo fue extendido, pero no fue posible actualizar la lista de sesiones.",
        );
      }
    } catch (extensionError) {
      setActionError(getExtensionErrorMessage(extensionError));
    } finally {
      setSessionActionId(null);
    }
  }

  /*
   * Finalizar una sesión
   */

  async function handleFinishSession(session: ActiveRegisteredSession) {
    const confirmed = window.confirm(
      `¿Finalizar la sesión de ${session.customer_display_name} en ${session.station_code}?`,
    );

    if (!confirmed) {
      return;
    }

    setSessionActionId(session.session_id);

    setActionError(null);

    setActionSuccess(null);

    try {
      const finishedSession = await finishRegisteredSession(session.session_id);

      setSessions((currentSessions) =>
        currentSessions.filter(
          (currentSession) => currentSession.session_id !== session.session_id,
        ),
      );

      setExtensionMinutes((current) => {
        const next = {
          ...current,
        };

        delete next[session.session_id];

        return next;
      });

      const historyUpdated = await loadHistory(
        historyOffset,
        historyCustomerId,
        historyStationId,
      );

      if (!historyUpdated) {
        setActionSuccess(
          "La sesión fue finalizada, pero no fue posible actualizar el historial.",
        );
      } else {
        setActionSuccess(
          `${session.station_code} finalizada: ${formatDuration(
            finishedSession.consumed_seconds,
          )} consumidos y ${formatDuration(
            finishedSession.released_seconds,
          )} devueltos.`,
        );
      }
    } catch (finishError) {
      setActionError(getFinishErrorMessage(finishError));
    } finally {
      setSessionActionId(null);
    }
  }

  return (
    <section className="sessions-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">GCMS Admin</p>

          <h1>Sesiones</h1>

          <p className="page-description">
            Supervisa las sesiones activas de clientes registrados. Las recargas
            se realizan desde Sala y el inicio de sesión no se ejecuta desde el
            panel administrativo.
          </p>
        </div>
      </header>

      {/* SESIONES ACTIVAS */}

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

        {actionError && (
          <p className="form-error" role="alert">
            {actionError}
          </p>
        )}

        {actionSuccess && (
          <p className="form-success" role="status">
            {actionSuccess}
          </p>
        )}

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
          <div className="content-state">Cargando sesiones activas...</div>
        ) : sessions.length === 0 ? (
          <div className="content-state">
            No hay sesiones REGISTERED activas.
          </div>
        ) : (
          <>
            <p className="results-count">Sesiones activas: {sessions.length}</p>

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

                    <th>Acciones</th>
                  </tr>
                </thead>

                <tbody>
                  {sessions.map((session) => (
                    <tr key={session.session_id}>
                      <td>
                        <strong>{session.station_code}</strong>
                      </td>

                      <td>
                        <strong>{session.customer_display_name}</strong>

                        <div className="table-secondary-text">
                          @{session.customer_username}
                        </div>
                      </td>

                      <td>
                        <span
                          className={
                            `session-time-state ` +
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
                        <div className="registered-session-actions">
                          <label className="session-extension-field">
                            <span>Agregar min</span>

                            <input
                              type="number"
                              min="1"
                              step="1"
                              value={extensionMinutes[session.session_id] ?? ""}
                              onChange={(event) =>
                                setExtensionMinutes((current) => ({
                                  ...current,

                                  [session.session_id]: event.target.value,
                                }))
                              }
                              placeholder="30"
                              disabled={sessionActionId === session.session_id}
                            />
                          </label>

                          <button
                            type="button"
                            className="secondary-button"
                            disabled={sessionActionId === session.session_id}
                            onClick={() => void handleExtendSession(session)}
                          >
                            {sessionActionId === session.session_id
                              ? "Procesando..."
                              : "Extender"}
                          </button>

                          <button
                            type="button"
                            className="danger-button"
                            disabled={sessionActionId === session.session_id}
                            onClick={() => void handleFinishSession(session)}
                          >
                            Finalizar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {/* HISTORIAL */}

      <section className="session-history-section">
        <div className="section-header">
          <div>
            <h2>Historial de sesiones</h2>

            <p className="page-description">Sesiones REGISTERED finalizadas.</p>
          </div>
        </div>

        <div className="session-history-filters">
          <label className="form-field">
            <span>Cliente</span>

            <select
              value={historyCustomerId}
              onChange={(event) => {
                setHistoryCustomerId(event.target.value);

                setHistoryOffset(0);
              }}
            >
              <option value="">Todos los clientes</option>

              {historyCustomers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.display_name}
                  {" · @"}
                  {customer.username}
                </option>
              ))}
            </select>
          </label>

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
            No hay sesiones finalizadas para estos filtros.
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Estación</th>

                    <th>Cliente</th>

                    <th>Autorizado</th>

                    <th>Consumido</th>

                    <th>Devuelto</th>

                    <th>Inicio</th>

                    <th>Fin</th>
                  </tr>
                </thead>

                <tbody>
                  {history.map((session) => (
                    <tr key={session.session_id}>
                      <td>
                        <strong>{session.station_code}</strong>
                      </td>

                      <td>
                        <strong>{session.customer_display_name}</strong>

                        <div className="table-secondary-text">
                          @{session.customer_username}
                        </div>
                      </td>

                      <td>{formatDuration(session.authorized_seconds)}</td>

                      <td>{formatDuration(session.consumed_seconds)}</td>

                      <td>{formatDuration(session.released_seconds)}</td>

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
                    Math.max(0, current - HISTORY_PAGE_SIZE),
                  )
                }
              >
                Anterior
              </button>

              <span>
                Página {Math.floor(historyOffset / HISTORY_PAGE_SIZE) + 1}
              </span>

              <button
                type="button"
                className="secondary-button"
                disabled={history.length < HISTORY_PAGE_SIZE}
                onClick={() =>
                  setHistoryOffset((current) => current + HISTORY_PAGE_SIZE)
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
