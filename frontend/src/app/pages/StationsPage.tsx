import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  createStation,
  listStations,
  updateStationStatus,
} from "../../features/stations/api";
import type {
  Station,
  StationStatus,
  AdminStationStatus,
} from "../../features/stations/types";
import { ApiError } from "../../lib/http";

const statusLabels: Record<StationStatus, string> = {
  AVAILABLE: "Disponible",
  IN_USE: "En uso",
  MAINTENANCE: "Mantenimiento",
  OFFLINE: "Fuera de línea",
};

const adminStatusOptions: {
  value: AdminStationStatus;
  label: string;
}[] = [
  {
    value: "AVAILABLE",
    label: "Disponible",
  },
  {
    value: "MAINTENANCE",
    label: "Mantenimiento",
  },
  {
    value: "OFFLINE",
    label: "Fuera de línea",
  },
];

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("es-CL");
}

export function StationsPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [newCode, setNewCode] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [updatingStationId, setUpdatingStationId] = useState<string | null>(
    null,
  );
  const [statusError, setStatusError] = useState<string | null>(null);
  const [statusSuccess, setStatusSuccess] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const loadStations = useCallback(
    async (showFullLoading = true): Promise<boolean> => {
      if (showFullLoading) {
        setIsLoading(true);
      }

      setError(null);

      try {
        const data = await listStations();
        setStations(data);

        return true;
      } catch {
        setError("No fue posible cargar las estaciones.");

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
    void loadStations();
  }, [loadStations]);

  async function handleCreateStation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const code = newCode.trim();

    if (!code) {
      setCreateError("Ingresa un código para la estación.");
      return;
    }

    if (code.length > 50) {
      setCreateError("El código no puede superar los 50 caracteres.");
      return;
    }

    setIsCreating(true);
    setCreateError(null);
    setCreateSuccess(null);

    try {
      const createdStation = await createStation({
        code,
      });

      setNewCode("");

      setCreateSuccess(
        `Estación ${createdStation.code} registrada correctamente.`,
      );

      const refreshed = await loadStations(false);

      if (!refreshed) {
        setCreateSuccess(
          `Estación ${createdStation.code} registrada, pero no fue posible actualizar el listado.`,
        );
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setCreateError("Ya existe una estación con ese código.");
      } else if (error instanceof ApiError && error.status === 422) {
        setCreateError("El código de estación no es válido.");
      } else {
        setCreateError("No fue posible registrar la estación.");
      }
    } finally {
      setIsCreating(false);
    }
  }
  async function handleRefreshStations() {
    setIsRefreshing(true);
    setStatusError(null);
    setStatusSuccess(null);

    const success = await loadStations(false);

    if (success) {
      setStatusSuccess("Listado de estaciones actualizado.");
    }

    setIsRefreshing(false);
  }
  async function handleStatusChange(
    station: Station,
    newStatus: AdminStationStatus,
  ) {
    if (station.status === newStatus) {
      return;
    }

    setUpdatingStationId(station.id);
    setStatusError(null);
    setStatusSuccess(null);

    try {
      const updatedStation = await updateStationStatus(station.id, newStatus);

      setStations((currentStations) =>
        currentStations.map((currentStation) =>
          currentStation.id === updatedStation.id
            ? updatedStation
            : currentStation,
        ),
      );

      setStatusSuccess(
        `${updatedStation.code} cambió a ${statusLabels[updatedStation.status]}.`,
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setStatusError("La estación ya no existe. Actualiza el listado.");
      } else if (error instanceof ApiError && error.status === 409) {
        setStatusError(
          "No se puede cambiar el estado porque la estación está en uso.",
        );
      } else if (error instanceof ApiError && error.status === 422) {
        setStatusError("Ese estado no se puede asignar manualmente.");
      } else {
        setStatusError("No fue posible cambiar el estado de la estación.");
      }
    } finally {
      setUpdatingStationId(null);
    }
  }

  return (
    <section className="stations-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">GCMS Admin</p>

          <h1>Estaciones</h1>

          <p className="page-description">
            Administra los equipos disponibles del gaming center.
          </p>
        </div>
      </header>

      <section className="station-registration-section">
        <div className="section-header">
          <div>
            <h2>Nueva estación</h2>

            <p className="page-description">
              Registra un nuevo computador para incorporarlo al sistema.
            </p>
          </div>
        </div>

        <form
          className="station-registration-form"
          onSubmit={handleCreateStation}
        >
          <label className="form-field">
            <span>Código de estación</span>

            <input
              type="text"
              value={newCode}
              onChange={(event) => setNewCode(event.target.value)}
              maxLength={50}
              placeholder="Ej: PC-01"
              autoComplete="off"
              disabled={isCreating}
            />
          </label>

          <button
            type="submit"
            className="primary-button"
            disabled={isCreating}
          >
            {isCreating ? "Registrando..." : "Registrar estación"}
          </button>
        </form>

        {createError && (
          <p className="form-error" role="alert">
            {createError}
          </p>
        )}

        {createSuccess && (
          <p className="form-success" role="status">
            {createSuccess}
          </p>
        )}
      </section>

      <section className="stations-list-section">
        <div className="section-header">
          <div>
            <h2>Equipos registrados</h2>

            <p className="page-description">
              Estado operativo actual de las estaciones.
            </p>
          </div>

          <button
            type="button"
            className="secondary-button"
            onClick={() => void handleRefreshStations()}
            disabled={isRefreshing}
          >
            {isRefreshing ? "Actualizando..." : "Actualizar"}
          </button>
        </div>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        {isLoading ? (
          <div className="content-state">Cargando estaciones...</div>
        ) : stations.length === 0 ? (
          <div className="content-state">
            Todavía no hay estaciones registradas.
          </div>
        ) : (
          <>
            <p className="results-count">
              Estaciones registradas: {stations.length}
            </p>

            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Estación</th>
                    <th>Estado</th>
                    <th>Registrada</th>
                    <th>Última actualización</th>
                    <th>Acciones</th>
                  </tr>
                </thead>

                <tbody>
                  {stations.map((station) => (
                    <tr key={station.id}>
                      <td>
                        <strong>{station.code}</strong>
                      </td>

                      <td>
                        <span
                          className={`station-status ${station.status.toLowerCase()}`}
                        >
                          {statusLabels[station.status]}
                        </span>
                      </td>

                      <td>{formatDateTime(station.created_at)}</td>

                      <td>{formatDateTime(station.updated_at)}</td>
                      <td>
                        {station.status === "IN_USE" ? (
                          <span className="station-managed-message">
                            Administrada por sesión
                          </span>
                        ) : (
                          <div className="station-actions">
                            {adminStatusOptions.map((option) => (
                              <button
                                key={option.value}
                                type="button"
                                className="station-action-button"
                                disabled={
                                  updatingStationId === station.id ||
                                  station.status === option.value
                                }
                                onClick={() =>
                                  void handleStatusChange(station, option.value)
                                }
                              >
                                {option.label}
                              </button>
                            ))}
                          </div>
                        )}
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
