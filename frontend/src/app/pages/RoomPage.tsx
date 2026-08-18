import { useCallback, useEffect, useState, type FormEvent } from "react";

import { listStations } from "../../features/stations/api";
import type { Station, StationStatus } from "../../features/stations/types";

import { listActiveRegisteredSessions } from "../../features/sessions/api";
import type { ActiveRegisteredSession } from "../../features/sessions/types";

import { listActiveGuestSessions } from "../../features/guest-sessions/api";
import type { ActiveGuestSession } from "../../features/guest-sessions/types";

import { ApiError } from "../../lib/http";

import { listActiveTimeProducts } from "../../features/time-products/api";
import type { TimeProduct } from "../../features/time-products/types";

import {
  createGuestTimeSale,
  createRegisteredTimeSale,
} from "../../features/time-sales/api";

import { listCustomers } from "../../features/customers/api";
import type { CustomerSummary } from "../../features/customers/types";

import { formatDuration } from "../../lib/time";

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
const clpFormatter = new Intl.NumberFormat("es-CL", {
  style: "currency",
  currency: "CLP",
  maximumFractionDigits: 0,
});

function formatPriceClp(priceClp: number): string {
  return clpFormatter.format(priceClp);
}

function getGuestSaleErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "No fue posible iniciar la sesión de invitado.";
  }

  switch (error.message) {
    case "Station is unavailable":
      return "La estación dejó de estar disponible. Actualiza Sala e inténtalo nuevamente.";

    case "Time product is inactive":
      return "La tarifa seleccionada ya no está activa.";

    case "Time product not found":
      return "La tarifa seleccionada ya no existe.";

    case "Guest session start conflict":
      return "No fue posible iniciar la sesión porque existe un conflicto con la estación.";

    default:
      return "No fue posible registrar la venta de invitado.";
  }
}

function getRegisteredSaleErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "No fue posible acreditar el tiempo al cliente.";
  }

  switch (error.message) {
    case "Time product is inactive":
      return "La tarifa seleccionada ya no está activa.";

    case "Time product not found":
      return "La tarifa seleccionada ya no existe.";

    case "Customer not found":
      return "El cliente seleccionado ya no existe.";

    case "Customer is inactive":
      return "No se puede recargar saldo a un cliente inactivo.";

    case "Customer wallet not found":
      return "El cliente no tiene un wallet disponible.";

    default:
      return "No fue posible registrar la venta del cliente.";
  }
}

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
  const [selectedGuestStation, setSelectedGuestStation] =
    useState<Station | null>(null);

  const [timeProducts, setTimeProducts] = useState<TimeProduct[]>([]);

  const [selectedTimeProductId, setSelectedTimeProductId] = useState<
    string | null
  >(null);

  const [isLoadingTimeProducts, setIsLoadingTimeProducts] = useState(false);

  const [isCreatingGuestSale, setIsCreatingGuestSale] = useState(false);

  const [guestSaleError, setGuestSaleError] = useState<string | null>(null);
  const [isRegisteredSaleOpen, setIsRegisteredSaleOpen] = useState(false);

  const [customerQuery, setCustomerQuery] = useState("");

  const [customerResults, setCustomerResults] = useState<CustomerSummary[]>([]);

  const [selectedCustomer, setSelectedCustomer] =
    useState<CustomerSummary | null>(null);

  const [isSearchingCustomers, setIsSearchingCustomers] = useState(false);

  const [customerSearchError, setCustomerSearchError] = useState<string | null>(
    null,
  );
  const [isCreatingRegisteredSale, setIsCreatingRegisteredSale] =
    useState(false);

  const [registeredSaleError, setRegisteredSaleError] = useState<string | null>(
    null,
  );

  const [registeredSaleSuccess, setRegisteredSaleSuccess] = useState<
    string | null
  >(null);

  const loadRoom = useCallback(
    async (showFullLoading = true): Promise<boolean> => {
      if (showFullLoading) {
        setIsLoading(true);
      }

      setError(null);

      try {
        const [stations, registeredSessions, guestSessions] = await Promise.all(
          [
            listStations(),
            listActiveRegisteredSessions(),
            listActiveGuestSessions(),
          ],
        );

        setRoomStations(
          buildRoomStations(stations, registeredSessions, guestSessions),
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
  async function handleOpenGuestSale(station: Station) {
    if (isCreatingRegisteredSale) {
      return;
    }

    setIsRegisteredSaleOpen(false);
    setCustomerQuery("");
    setCustomerResults([]);
    setSelectedCustomer(null);
    setCustomerSearchError(null);

    setSelectedGuestStation(station);
    setTimeProducts([]);
    setSelectedTimeProductId(null);
    setGuestSaleError(null);
    setIsLoadingTimeProducts(true);

    try {
      const products = await listActiveTimeProducts();

      setTimeProducts(products);
    } catch {
      setGuestSaleError("No fue posible cargar las tarifas activas.");
    } finally {
      setIsLoadingTimeProducts(false);
    }
  }
  function handleCloseGuestSale() {
    if (isCreatingGuestSale) {
      return;
    }

    setSelectedGuestStation(null);
    setTimeProducts([]);
    setSelectedTimeProductId(null);
    setGuestSaleError(null);
  }

  async function handleOpenRegisteredSale() {
    if (isCreatingGuestSale) {
      return;
    }

    setSelectedGuestStation(null);
    setGuestSaleError(null);

    setIsRegisteredSaleOpen(true);
    setCustomerQuery("");
    setCustomerResults([]);
    setSelectedCustomer(null);
    setCustomerSearchError(null);

    setTimeProducts([]);
    setSelectedTimeProductId(null);

    setRegisteredSaleError(null);
    setRegisteredSaleSuccess(null);

    setIsLoadingTimeProducts(true);

    try {
      const products = await listActiveTimeProducts();

      setTimeProducts(products);
    } catch {
      setRegisteredSaleError("No fue posible cargar las tarifas activas.");
    } finally {
      setIsLoadingTimeProducts(false);
    }
  }

  function handleCloseRegisteredSale() {
    if (isCreatingRegisteredSale) {
      return;
    }

    setIsRegisteredSaleOpen(false);

    setCustomerQuery("");
    setCustomerResults([]);
    setSelectedCustomer(null);
    setCustomerSearchError(null);

    setTimeProducts([]);
    setSelectedTimeProductId(null);

    setRegisteredSaleError(null);
    setRegisteredSaleSuccess(null);
  }

  async function handleSearchCustomers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const query = customerQuery.trim();

    if (query.length === 0) {
      setCustomerSearchError("Ingresa un nombre o usuario para buscar.");
      return;
    }

    setIsSearchingCustomers(true);
    setCustomerSearchError(null);
    setSelectedCustomer(null);
    setSelectedTimeProductId(null);
    setRegisteredSaleError(null);
    setRegisteredSaleSuccess(null);

    try {
      const customers = await listCustomers({
        q: query,
        isActive: true,
        limit: 10,
        offset: 0,
      });

      setCustomerResults(customers);
    } catch {
      setCustomerSearchError("No fue posible buscar clientes.");
    } finally {
      setIsSearchingCustomers(false);
    }
  }

  function handleSelectCustomer(customer: CustomerSummary) {
    setSelectedCustomer(customer);
    setSelectedTimeProductId(null);

    setCustomerSearchError(null);
    setRegisteredSaleError(null);
    setRegisteredSaleSuccess(null);
  }

  async function handleCreateRegisteredSale() {
    if (selectedCustomer === null || selectedTimeProductId === null) {
      return;
    }

    setIsCreatingRegisteredSale(true);
    setRegisteredSaleError(null);
    setRegisteredSaleSuccess(null);

    try {
      const response = await createRegisteredTimeSale({
        sale_type: "REGISTERED",
        time_product_id: selectedTimeProductId,
        customer_id: selectedCustomer.id,
      });

      const updatedCustomer: CustomerSummary = {
        ...selectedCustomer,
        available_seconds: response.available_seconds,
        reserved_seconds: response.reserved_seconds,
      };

      setSelectedCustomer(updatedCustomer);

      setCustomerResults((currentCustomers) =>
        currentCustomers.map((customer) =>
          customer.id === updatedCustomer.id ? updatedCustomer : customer,
        ),
      );

      setSelectedTimeProductId(null);

      setRegisteredSaleSuccess(
        `${response.product_name} acreditado correctamente. Nuevo saldo: ${formatDuration(
          response.available_seconds,
        )}.`,
      );
    } catch (saleError) {
      setRegisteredSaleError(getRegisteredSaleErrorMessage(saleError));
    } finally {
      setIsCreatingRegisteredSale(false);
    }
  }

  async function handleCreateGuestSale() {
    if (selectedGuestStation === null || selectedTimeProductId === null) {
      return;
    }

    setIsCreatingGuestSale(true);
    setGuestSaleError(null);

    try {
      await createGuestTimeSale({
        sale_type: "GUEST",
        time_product_id: selectedTimeProductId,
        station_id: selectedGuestStation.id,
      });

      setSelectedGuestStation(null);
      setTimeProducts([]);
      setSelectedTimeProductId(null);

      await loadRoom(false);
    } catch (saleError) {
      setGuestSaleError(getGuestSaleErrorMessage(saleError));
    } finally {
      setIsCreatingGuestSale(false);
    }
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

        <div className="room-header-actions">
          <button
            type="button"
            className="primary-button"
            onClick={() => void handleOpenRegisteredSale()}
            disabled={isCreatingGuestSale || isCreatingRegisteredSale}
          >
            Recargar cliente
          </button>

          <button
            type="button"
            className="secondary-button"
            onClick={() => void handleRefresh()}
            disabled={isRefreshing}
          >
            {isRefreshing ? "Actualizando..." : "Actualizar"}
          </button>
        </div>
      </header>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {isLoading ? (
        <div className="content-state">Cargando estado de la sala...</div>
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
          {isRegisteredSaleOpen && (
            <section className="room-registered-sale-panel">
              <header className="room-registered-sale-header">
                <div>
                  <p className="eyebrow">Venta REGISTERED</p>

                  <h2>Recargar cliente</h2>

                  <p className="page-description">
                    Busca la cuenta del cliente que comprará tiempo.
                  </p>
                </div>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleCloseRegisteredSale}
                  disabled={isSearchingCustomers || isCreatingRegisteredSale}
                >
                  Cancelar
                </button>
              </header>

              <form
                className="room-customer-search"
                onSubmit={(event) => void handleSearchCustomers(event)}
              >
                <input
                  type="search"
                  value={customerQuery}
                  onChange={(event) => setCustomerQuery(event.target.value)}
                  placeholder="Buscar por nombre o usuario"
                  autoComplete="off"
                  disabled={isSearchingCustomers}
                />

                <button
                  type="submit"
                  className="primary-button"
                  disabled={isSearchingCustomers}
                >
                  {isSearchingCustomers ? "Buscando..." : "Buscar"}
                </button>
              </form>

              {customerSearchError && (
                <p className="form-error" role="alert">
                  {customerSearchError}
                </p>
              )}

              {!isSearchingCustomers && customerResults.length > 0 && (
                <div className="room-customer-results">
                  {customerResults.map((customer) => {
                    const isSelected = selectedCustomer?.id === customer.id;

                    return (
                      <button
                        key={customer.id}
                        type="button"
                        className={`room-customer-option ${
                          isSelected ? "selected" : ""
                        }`}
                        aria-pressed={isSelected}
                        onClick={() => handleSelectCustomer(customer)}
                      >
                        <div>
                          <strong>{customer.display_name}</strong>

                          <span>@{customer.username}</span>
                        </div>

                        <div className="room-customer-balance">
                          <span>Saldo disponible</span>

                          <strong>
                            {formatDuration(customer.available_seconds)}
                          </strong>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}

              {!isSearchingCustomers &&
                customerQuery.trim().length > 0 &&
                customerResults.length === 0 &&
                customerSearchError === null && (
                  <div className="content-state">
                    No se encontraron clientes activos.
                  </div>
                )}

              {selectedCustomer && (
                <section className="room-selected-customer">
                  <div>
                    <span className="summary-label">Cliente seleccionado</span>

                    <strong>{selectedCustomer.display_name}</strong>

                    <span>@{selectedCustomer.username}</span>
                  </div>

                  <div>
                    <span className="summary-label">Saldo actual</span>

                    <strong>
                      {formatDuration(selectedCustomer.available_seconds)}
                    </strong>
                  </div>
                </section>
              )}
              {registeredSaleError && (
                <p className="form-error" role="alert">
                  {registeredSaleError}
                </p>
              )}

              {registeredSaleSuccess && (
                <p className="form-success" role="status">
                  {registeredSaleSuccess}
                </p>
              )}

              {isLoadingTimeProducts ? (
                <div className="content-state">Cargando tarifas...</div>
              ) : timeProducts.length === 0 ? (
                <div className="content-state">
                  No hay tarifas activas disponibles.
                </div>
              ) : (
                <>
                  <div className="room-product-grid">
                    {timeProducts.map((product) => {
                      const isSelected = selectedTimeProductId === product.id;

                      return (
                        <button
                          key={product.id}
                          type="button"
                          className={`room-product-option ${
                            isSelected ? "selected" : ""
                          }`}
                          aria-pressed={isSelected}
                          disabled={isCreatingRegisteredSale}
                          onClick={() => {
                            setSelectedTimeProductId(product.id);
                            setRegisteredSaleError(null);
                            setRegisteredSaleSuccess(null);
                          }}
                        >
                          <strong>{product.name}</strong>

                          <span>
                            {formatRemainingTime(product.duration_seconds)}
                          </span>

                          <span className="room-product-price">
                            {formatPriceClp(product.price_clp)}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  <div className="room-guest-sale-actions">
                    <button
                      type="button"
                      className="primary-button"
                      onClick={() => void handleCreateRegisteredSale()}
                      disabled={
                        selectedTimeProductId === null ||
                        isCreatingRegisteredSale
                      }
                    >
                      {isCreatingRegisteredSale
                        ? "Acreditando..."
                        : "Cobrar y acreditar"}
                    </button>
                  </div>
                </>
              )}
            </section>
          )}
          {selectedGuestStation && (
            <section className="room-guest-sale-panel">
              <header className="room-guest-sale-header">
                <div>
                  <p className="eyebrow">Venta GUEST</p>

                  <h2>Iniciar invitado en {selectedGuestStation.code}</h2>

                  <p className="page-description">
                    Selecciona la tarifa que pagará el cliente.
                  </p>
                </div>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleCloseGuestSale}
                  disabled={isCreatingGuestSale}
                >
                  Cancelar
                </button>
              </header>

              {guestSaleError && (
                <p className="form-error" role="alert">
                  {guestSaleError}
                </p>
              )}

              {isLoadingTimeProducts ? (
                <div className="content-state">Cargando tarifas...</div>
              ) : timeProducts.length === 0 ? (
                <div className="content-state">
                  No hay tarifas activas disponibles.
                </div>
              ) : (
                <>
                  <div className="room-product-grid">
                    {timeProducts.map((product) => {
                      const isSelected = selectedTimeProductId === product.id;

                      return (
                        <button
                          key={product.id}
                          type="button"
                          className={`room-product-option ${
                            isSelected ? "selected" : ""
                          }`}
                          aria-pressed={isSelected}
                          onClick={() => setSelectedTimeProductId(product.id)}
                          disabled={isCreatingGuestSale}
                        >
                          <strong>{product.name}</strong>

                          <span>
                            {formatRemainingTime(product.duration_seconds)}
                          </span>

                          <span className="room-product-price">
                            {formatPriceClp(product.price_clp)}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  <div className="room-guest-sale-actions">
                    <button
                      type="button"
                      className="primary-button"
                      onClick={() => void handleCreateGuestSale()}
                      disabled={
                        selectedTimeProductId === null || isCreatingGuestSale
                      }
                    >
                      {isCreatingGuestSale
                        ? "Registrando venta..."
                        : "Cobrar e iniciar"}
                    </button>
                  </div>
                </>
              )}
            </section>
          )}

          <section className="room-grid">
            {roomStations.map(({ station, session }) => (
              <article
                key={station.id}
                className={`room-station-card ${station.status
                  .toLowerCase()
                  .replace("_", "-")} ${
                  selectedGuestStation?.id === station.id ? "selected" : ""
                }`}
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
                      <p className="room-station-main-status">Disponible</p>

                      <p className="room-station-secondary">Lista para usar</p>

                      <button
                        type="button"
                        className="room-guest-start-button"
                        onClick={() => void handleOpenGuestSale(station)}
                        disabled={isCreatingRegisteredSale}
                      >
                        Iniciar invitado
                      </button>
                    </>
                  )}

                  {station.status === "MAINTENANCE" && (
                    <>
                      <p className="room-station-main-status">Mantenimiento</p>

                      <p className="room-station-secondary">
                        Equipo no disponible
                      </p>
                    </>
                  )}

                  {station.status === "OFFLINE" && (
                    <>
                      <p className="room-station-main-status">Fuera de línea</p>

                      <p className="room-station-secondary">
                        Equipo no disponible
                      </p>
                    </>
                  )}

                  {station.status === "IN_USE" && session === null && (
                    <>
                      <p className="room-station-main-status">En uso</p>

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
                            {formatRemainingTime(session.remainingSeconds)}
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

                  {station.status === "IN_USE" && session?.type === "GUEST" && (
                    <>
                      <div className="room-session-type">
                        <span>Invitado</span>
                      </div>

                      <p className="room-station-customer">Invitado</p>

                      <div className="room-time">
                        <span className="room-time-label">Tiempo restante</span>

                        <strong>
                          {formatRemainingTime(session.remainingSeconds)}
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
