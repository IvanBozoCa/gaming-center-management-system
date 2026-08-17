import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  listActiveRegisteredSessions,
  startRegisteredSession,
} from "../../features/sessions/api";
import type {
  ActiveRegisteredSession,
  SessionTimeState,
} from "../../features/sessions/types";
import { formatDuration } from "../../lib/time";
import { listCustomers } from "../../features/customers/api";
import type { CustomerSummary } from "../../features/customers/types";

import { listStations } from "../../features/stations/api";
import type { Station } from "../../features/stations/types";

import { ApiError } from "../../lib/http";

const timeStateLabels: Record<SessionTimeState, string> = {
  RUNNING: "En curso",
  EXHAUSTED: "Sin tiempo · activa",
};

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("es-CL");
}

export function SessionsPage() {
  const [sessions, setSessions] = useState<ActiveRegisteredSession[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [stations, setStations] = useState<Station[]>([]);

  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [selectedStationId, setSelectedStationId] = useState("");
  const [authorizedMinutes, setAuthorizedMinutes] = useState("");

  const [isLoadingOptions, setIsLoadingOptions] = useState(true);
  const [isStarting, setIsStarting] = useState(false);

  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [startSuccess, setStartSuccess] = useState<string | null>(null);

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
  const loadStartOptions = useCallback(async (): Promise<boolean> => {
    setIsLoadingOptions(true);
    setOptionsError(null);

    try {
      const [customerData, stationData] = await Promise.all([
        listCustomers({
          isActive: true,
          limit: 100,
        }),
        listStations(),
      ]);

      setCustomers(customerData);

      setStations(
        stationData.filter((station) => station.status === "AVAILABLE"),
      );

      return true;
    } catch {
      setOptionsError(
        "No fue posible cargar clientes y estaciones disponibles.",
      );

      return false;
    } finally {
      setIsLoadingOptions(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);
  useEffect(() => {
    void loadStartOptions();
  }, [loadStartOptions]);

  async function handleRefresh() {
    setIsRefreshing(true);
    setFeedback(null);

    const success = await loadSessions(false);

    if (success) {
      setFeedback("Sesiones activas actualizadas.");
    }

    setIsRefreshing(false);
  }

  async function handleStartSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const minutes = Number(authorizedMinutes);

    if (!selectedCustomerId) {
      setStartError("Selecciona un cliente.");
      return;
    }

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
    setStartSuccess(null);

    try {
      const startedSession = await startRegisteredSession({
        customer_id: selectedCustomerId,
        station_id: selectedStationId,
        authorized_seconds: authorizedSeconds,
      });

      setSelectedCustomerId("");
      setSelectedStationId("");
      setAuthorizedMinutes("");

      setStartSuccess(
        `Sesión iniciada correctamente por ${formatDuration(
          startedSession.authorized_seconds,
        )}.`,
      );

      const [sessionsUpdated, optionsUpdated] = await Promise.all([
        loadSessions(false),
        loadStartOptions(),
      ]);

      if (!sessionsUpdated || !optionsUpdated) {
        setStartSuccess(
          "La sesión fue iniciada, pero no fue posible actualizar toda la pantalla.",
        );
      }
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 404) {
          setStartError("El cliente o la estación ya no existen.");
        } else if (
          error.status === 409 &&
          error.message === "Insufficient time balance"
        ) {
          setStartError("El cliente no tiene tiempo disponible suficiente.");
        } else if (
          error.status === 409 &&
          error.message === "Station is not available"
        ) {
          setStartError("La estación seleccionada ya no está disponible.");
        } else if (
          error.status === 409 &&
          error.message === "Customer is inactive"
        ) {
          setStartError("El cliente seleccionado está inactivo.");
        } else if (
          error.status === 409 &&
          error.message === "Station already has an active session"
        ) {
          setStartError("La estación ya tiene una sesión activa.");
        } else if (
          error.status === 409 &&
          error.message === "Customer already has an active session"
        ) {
          setStartError("El cliente ya tiene una sesión activa.");
        } else if (error.status === 409) {
          setStartError(
            "No fue posible iniciar la sesión por un conflicto de estado.",
          );
        } else if (error.status === 422) {
          setStartError("El tiempo autorizado no es válido.");
        } else {
          setStartError("No fue posible iniciar la sesión.");
        }
      } else {
        setStartError("No fue posible iniciar la sesión.");
      }
    } finally {
      setIsStarting(false);
    }
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
      <section className="session-start-section">
        <div className="section-header">
          <div>
            <h2>Iniciar sesión</h2>

            <p className="page-description">
              Asigna un cliente registrado a una estación disponible.
            </p>
          </div>
        </div>

        {optionsError && (
          <p className="form-error" role="alert">
            {optionsError}
          </p>
        )}

        <form className="session-start-form" onSubmit={handleStartSession}>
          <label className="form-field">
            <span>Cliente</span>

            <select
              value={selectedCustomerId}
              onChange={(event) => setSelectedCustomerId(event.target.value)}
              disabled={isLoadingOptions || isStarting}
            >
              <option value="">Selecciona un cliente</option>

              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.display_name}
                  {" · "}
                  {formatDuration(customer.available_seconds)}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span>Estación</span>

            <select
              value={selectedStationId}
              onChange={(event) => setSelectedStationId(event.target.value)}
              disabled={isLoadingOptions || isStarting}
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
            disabled={
              isStarting ||
              isLoadingOptions ||
              customers.length === 0 ||
              stations.length === 0
            }
          >
            {isStarting ? "Iniciando..." : "Iniciar sesión"}
          </button>
        </form>

        {startError && (
          <p className="form-error" role="alert">
            {startError}
          </p>
        )}

        {startSuccess && (
          <p className="form-success" role="status">
            {startSuccess}
          </p>
        )}
      </section>

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
