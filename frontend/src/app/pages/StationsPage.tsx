import { useCallback, useEffect, useState, type FormEvent } from "react";

import { createStation, listStations } from "../../features/stations/api";
import type { Station, StationStatus } from "../../features/stations/types";
import { ApiError } from "../../lib/http";

const statusLabels: Record<StationStatus, string> = {
  AVAILABLE: "Disponible",
  IN_USE: "En uso",
  MAINTENANCE: "Mantenimiento",
  OFFLINE: "Fuera de línea",
};

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("es-CL");
}

export function StationsPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [newCode, setNewCode] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);

  const loadStations = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await listStations();
      setStations(data);
    } catch {
      setError("No fue posible cargar las estaciones.");
    } finally {
      setIsLoading(false);
    }
  }, []);

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

      await loadStations();
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
