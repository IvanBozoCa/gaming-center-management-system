import { useCallback, useEffect, useState } from "react";

import { listStations } from "../../features/stations/api";
import type {
  Station,
  StationStatus,
} from "../../features/stations/types";

import { listActiveRegisteredSessions } from "../../features/sessions/api";
import type { ActiveRegisteredSession } from "../../features/sessions/types";

import { listActiveGuestSessions } from "../../features/guest-sessions/api";
import type { ActiveGuestSession } from "../../features/guest-sessions/types";

type RoomSession =
  | {
      type: "REGISTERED";
      sessionId: string;
      customerName: string;
      remainingSeconds: number;
      timeState: ActiveRegisteredSession["time_state"];
    }
  | {
      type: "GUEST";
      sessionId: string;
      remainingSeconds: number;
      timeState: ActiveGuestSession["time_state"];
    };

interface RoomStation {
  station: Station;
  session: RoomSession | null;
}

const stationStatusLabels: Record<StationStatus, string> = {
  AVAILABLE: "Disponible",
  IN_USE: "En uso",
  MAINTENANCE: "Mantenimiento",
  OFFLINE: "Fuera de línea",
};

function formatRemainingTime(seconds: number): string {
  const safeSeconds = Math.max(0, seconds);

  if (safeSeconds === 0) {
    return "Sin tiempo";
  }

  const totalMinutes = Math.floor(safeSeconds / 60);

  if (totalMinutes === 0) {
    return "< 1 min";
  }

  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) {
    return `${minutes} min`;
  }

  if (minutes === 0) {
    return `${hours} h`;
  }

  return `${hours} h ${minutes} min`;
}

function buildRoomStations(
  stations: Station[],
  registeredSessions: ActiveRegisteredSession[],
  guestSessions: ActiveGuestSession[],
): RoomStation[] {
  const registeredByStationId = new Map(
    registeredSessions.map((session) => [session.station_id, session]),
  );

  const guestByStationId = new Map(
    guestSessions.map((session) => [session.station_id, session]),
  );

  return [...stations]
    .sort((firstStation, secondStation) =>
      firstStation.code.localeCompare(secondStation.code, "es", {
        numeric: true,
        sensitivity: "base",
      }),
    )
    .map((station) => {
      const registeredSession = registeredByStationId.get(station.id);

      if (registeredSession) {
        return {
          station,
          session: {
            type: "REGISTERED",
            sessionId: registeredSession.session_id,
            customerName: registeredSession.customer_display_name,
            remainingSeconds: registeredSession.remaining_seconds,
            timeState: registeredSession.time_state,
          },
        };
      }

      const guestSession = guestByStationId.get(station.id);

      if (guestSession) {
        return {
          station,
          session: {
            type: "GUEST",
            sessionId: guestSession.session_id,
            remainingSeconds: guestSession.remaining_seconds,
            timeState: guestSession.time_state,
          },
        };
      }

      return {
        station,
        session: null,
      };
    });
}

export function RoomPage() {
  const [roomStations, setRoomStations] = useState<RoomStation[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRoom = useCallback(
    async (showFullLoading = true): Promise<boolean> => {
      if (showFullLoading) {
        setIsLoading(true);
      }

      setError(null);

      try {
        const [
          stations,
          registeredSessions,
          guestSessions,
        ] = await Promise.all([
          listStations(),
          listActiveRegisteredSessions(),
          listActiveGuestSessions(),
        ]);

        setRoomStations(
          buildRoomStations(
            stations,
            registeredSessions,
            guestSessions,
          ),
        );

        return true;
      } catch {
        setError("No fue posible cargar el estado de la sala.");

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
    void loadRoom();
  }, [loadRoom]);

  async function handleRefresh() {
    setIsRefreshing(true);

    await loadRoom(false);

    setIsRefreshing(false);
  }

  const summary = roomStations.reduce<Record<StationStatus, number>>(
    (currentSummary, roomStation) => {
      currentSummary[roomStation.station.status] += 1;
      return currentSummary;
    },
    {
      AVAILABLE: 0,
      IN_USE: 0,
      MAINTENANCE: 0,
      OFFLINE: 0,
    },
  );

  return (
    <section className="room-page">
      <header className="page-header room-page-header">
        <div>
          <p className="eyebrow">GCMS Admin</p>

          <h1>Sala</h1>

          <p className="page-description">
            Estado operativo actual de los computadores del gaming center.
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
      </header>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {isLoading ? (
        <div className="content-state">
          Cargando estado de la sala...
        </div>
      ) : roomStations.length === 0 ? (
        <div className="content-state">
          Todavía no hay estaciones registradas.
        </div>
      ) : (
        <>
          <section className="room-summary">
            <article className="room-summary-card available">
              <strong>{summary.AVAILABLE}</strong>
              <span>Disponibles</span>
            </article>

            <article className="room-summary-card in-use">
              <strong>{summary.IN_USE}</strong>
              <span>En uso</span>
            </article>

            <article className="room-summary-card maintenance">
              <strong>{summary.MAINTENANCE}</strong>
              <span>Mantenimiento</span>
            </article>

            <article className="room-summary-card offline">
              <strong>{summary.OFFLINE}</strong>
              <span>Fuera de línea</span>
            </article>
          </section>

          <section className="room-grid">
            {roomStations.map(({ station, session }) => (
              <article
                key={station.id}
                className={`room-station-card ${station.status
                  .toLowerCase()
                  .replace("_", "-")}`}
              >
                <header className="room-station-header">
                  <h2>{station.code}</h2>

                  <span
                    className={`station-status ${station.status.toLowerCase()}`}
                  >
                    {stationStatusLabels[station.status]}
                  </span>
                </header>

                <div className="room-station-content">
                  {station.status === "AVAILABLE" && (
                    <>
                      <p className="room-station-main-status">
                        Disponible
                      </p>

                      <p className="room-station-secondary">
                        Lista para usar
                      </p>
                    </>
                  )}

                  {station.status === "MAINTENANCE" && (
                    <>
                      <p className="room-station-main-status">
                        Mantenimiento
                      </p>

                      <p className="room-station-secondary">
                        Equipo no disponible
                      </p>
                    </>
                  )}

                  {station.status === "OFFLINE" && (
                    <>
                      <p className="room-station-main-status">
                        Fuera de línea
                      </p>

                      <p className="room-station-secondary">
                        Equipo no disponible
                      </p>
                    </>
                  )}

                  {station.status === "IN_USE" && session === null && (
                    <>
                      <p className="room-station-main-status">
                        En uso
                      </p>

                      <p className="room-station-secondary">
                        No se encontró una sesión activa asociada.
                      </p>
                    </>
                  )}

                  {station.status === "IN_USE" &&
                    session?.type === "REGISTERED" && (
                      <>
                        <div className="room-session-type">
                          <span>Registrado</span>
                        </div>

                        <p className="room-station-customer">
                          {session.customerName}
                        </p>

                        <div className="room-time">
                          <span className="room-time-label">
                            Tiempo restante
                          </span>

                          <strong>
                            {formatRemainingTime(
                              session.remainingSeconds,
                            )}
                          </strong>
                        </div>

                        <span
                          className={`session-time-state ${session.timeState.toLowerCase()}`}
                        >
                          {session.timeState === "RUNNING"
                            ? "En curso"
                            : "Tiempo agotado"}
                        </span>
                      </>
                    )}

                  {station.status === "IN_USE" &&
                    session?.type === "GUEST" && (
                      <>
                        <div className="room-session-type">
                          <span>Invitado</span>
                        </div>

                        <p className="room-station-customer">
                          Invitado
                        </p>

                        <div className="room-time">
                          <span className="room-time-label">
                            Tiempo restante
                          </span>

                          <strong>
                            {formatRemainingTime(
                              session.remainingSeconds,
                            )}
                          </strong>
                        </div>

                        <span
                          className={`session-time-state ${session.timeState.toLowerCase()}`}
                        >
                          {session.timeState === "RUNNING"
                            ? "En curso"
                            : "Tiempo agotado"}
                        </span>
                      </>
                    )}
                </div>
              </article>
            ))}
          </section>
        </>
      )}
    </section>
  );
}