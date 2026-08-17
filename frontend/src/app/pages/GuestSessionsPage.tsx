import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  finishGuestSession,
  listActiveGuestSessions,
  startGuestSession,
} from "../../features/guest-sessions/api";

import type {
  ActiveGuestSession,
  GuestSessionTimeState,
} from "../../features/guest-sessions/types";

import { listStations } from "../../features/stations/api";
import type { Station } from "../../features/stations/types";

import { ApiError } from "../../lib/http";
import { formatDuration } from "../../lib/time";

const timeStateLabels: Record<GuestSessionTimeState, string> = {
  RUNNING: "En curso",
  EXHAUSTED: "Sin tiempo · activa",
};

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("es-CL");
}

function getStartErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "No fue posible iniciar la sesión de invitado.";
  }

  if (error.status === 404) {
    return "La estación seleccionada ya no existe.";
  }

  if (error.status === 422) {
    return "El tiempo autorizado debe ser mayor que cero.";
  }

  if (error.status === 409 && error.message === "Station is not available") {
    return "La estación seleccionada ya no está disponible.";
  }

  if (
    error.status === 409 &&
    error.message === "Station already has an active session"
  ) {
    return "La estación ya tiene una sesión activa.";
  }

  if (error.status === 409) {
    return "No fue posible iniciar la sesión por un conflicto de estado.";
  }

  return "No fue posible iniciar la sesión de invitado.";
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
  const [sessions, setSessions] = useState<ActiveGuestSession[]>([]);
  const [stations, setStations] = useState<Station[]>([]);

  const [selectedStationId, setSelectedStationId] = useState("");
  const [authorizedMinutes, setAuthorizedMinutes] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingStations, setIsLoadingStations] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [stationError, setStationError] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [finishingSessionId, setFinishingSessionId] = useState<string | null>(
    null,
  );

  const [finishError, setFinishError] = useState<string | null>(null);

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
  const loadAvailableStations = useCallback(async (): Promise<boolean> => {
    setIsLoadingStations(true);
    setStationError(null);

    try {
      const data = await listStations();

      setStations(data.filter((station) => station.status === "AVAILABLE"));

      return true;
    } catch {
      setStationError("No fue posible cargar las estaciones disponibles.");

      return false;
    } finally {
      setIsLoadingStations(false);
    }
  }, []);
  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    void loadAvailableStations();
  }, [loadAvailableStations]);
  async function handleRefresh() {
    setIsRefreshing(true);
    setFeedback(null);

    const [sessionsUpdated, stationsUpdated] = await Promise.all([
      loadSessions(false),
      loadAvailableStations(),
    ]);

    if (sessionsUpdated && stationsUpdated) {
      setFeedback("Sesiones y estaciones actualizadas.");
    }

    setIsRefreshing(false);
  }
  async function handleStartSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const minutes = Number(authorizedMinutes);

    if (!selectedStationId) {
      setStartError("Selecciona una estación.");
      return;
    }

    if (!Number.isFinite(minutes) || minutes <= 0) {
      setStartError("El tiempo autorizado debe ser mayor que cero.");
      return;
    }

    const authorizedSeconds = Math.floor(minutes * 60);

    setIsStarting(true);
    setStartError(null);
    setFeedback(null);

    try {
      const startedSession = await startGuestSession({
        station_id: selectedStationId,
        authorized_seconds: authorizedSeconds,
      });

      setSelectedStationId("");
      setAuthorizedMinutes("");

      const [sessionsUpdated, stationsUpdated] = await Promise.all([
        loadSessions(false),
        loadAvailableStations(),
      ]);

      if (!sessionsUpdated || !stationsUpdated) {
        setFeedback(
          "La sesión fue iniciada, pero no fue posible actualizar toda la pantalla.",
        );
      } else {
        setFeedback(
          `Sesión GUEST iniciada por ${formatDuration(
            startedSession.authorized_seconds,
          )}.`,
        );
      }
    } catch (error) {
      setStartError(getStartErrorMessage(error));
    } finally {
      setIsStarting(false);
    }
  }
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

      const stationsUpdated = await loadAvailableStations();

      if (!stationsUpdated) {
        setFeedback(
          "La sesión fue finalizada, pero no fue posible actualizar las estaciones.",
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
    } catch (error) {
      setFinishError(getFinishErrorMessage(error));
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
            Inicia y supervisa sesiones temporales para usuarios sin cuenta.
          </p>
        </div>
      </header>

      <section className="session-start-section">
        <div className="section-header">
          <div>
            <h2>Nueva sesión GUEST</h2>

            <p className="page-description">
              Selecciona una estación disponible y asigna tiempo de uso.
            </p>
          </div>
        </div>

        {stationError && (
          <p className="form-error" role="alert">
            {stationError}
          </p>
        )}

        <form
          className="session-start-form guest-session-start-form"
          onSubmit={handleStartSession}
        >
          <label className="form-field">
            <span>Estación</span>

            <select
              value={selectedStationId}
              onChange={(event) => setSelectedStationId(event.target.value)}
              disabled={isLoadingStations || isStarting}
            >
              <option value="">Selecciona una estación</option>

              {stations.map((station) => (
                <option key={station.id} value={station.id}>
                  {station.code}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span>Minutos</span>

            <input
              type="number"
              min="1"
              step="1"
              value={authorizedMinutes}
              onChange={(event) => setAuthorizedMinutes(event.target.value)}
              placeholder="Ej: 60"
              disabled={isStarting}
            />
          </label>

          <button
            type="submit"
            className="primary-button"
            disabled={isStarting || isLoadingStations || stations.length === 0}
          >
            {isStarting ? "Iniciando..." : "Iniciar invitado"}
          </button>
        </form>

        {startError && (
          <p className="form-error" role="alert">
            {startError}
          </p>
        )}
      </section>

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

                    <td>{formatDuration(session.remaining_seconds)}</td>

                    <td>{formatDateTime(session.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}
