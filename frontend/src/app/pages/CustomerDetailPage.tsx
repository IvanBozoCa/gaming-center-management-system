import {
  useEffect,
  useState,
  type FormEvent,
} from "react";
import {
  Link,
  useParams,
} from "react-router";

import {
  getCustomer,
  getCustomerWallet,
  listCustomerTransactions,
  purchaseCustomerTime,
} from "../../features/customers/api";
import type {
  CustomerDetail,
  TimeTransaction,
  TimeTransactionType,
  TimeWallet,
} from "../../features/customers/types";
import { ApiError } from "../../lib/http";
import {
  formatDuration,
  formatSignedDuration,
} from "../../lib/time";

const PAGE_SIZE = 20;

const transactionLabels:
  Record<TimeTransactionType, string> = {
    PURCHASE: "Compra",
    SESSION_RESERVE: "Reserva de sesión",
    SESSION_USAGE: "Uso de sesión",
    SESSION_RELEASE: "Liberación de reserva",
    BONUS: "Bonificación",
    ADJUSTMENT: "Ajuste",
    REFUND: "Devolución",
  };

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString(
    "es-CL",
  );
}

export function CustomerDetailPage() {
  const { customerId } = useParams<{
    customerId: string;
  }>();

  const [customer, setCustomer] =
    useState<CustomerDetail | null>(null);

  const [wallet, setWallet] =
    useState<TimeWallet | null>(null);

  const [transactions, setTransactions] =
    useState<TimeTransaction[]>([]);

  const [offset, setOffset] =
    useState(0);

  const [isLoadingCustomer, setIsLoadingCustomer] =
    useState(true);

  const [isLoadingTransactions, setIsLoadingTransactions] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [purchaseMinutes, setPurchaseMinutes] =
    useState("");

  const [isPurchasing, setIsPurchasing] =
    useState(false);

  const [purchaseError, setPurchaseError] =
    useState<string | null>(null);

  const [purchaseSuccess, setPurchaseSuccess] =
    useState<string | null>(null);

  useEffect(() => {
    if (!customerId) {
      return;
    }

    let cancelled = false;

    async function loadCustomer() {
      setIsLoadingCustomer(true);
      setError(null);

      try {
        const [
          customerData,
          walletData,
        ] = await Promise.all([
          getCustomer(customerId!),
          getCustomerWallet(customerId!),
        ]);

        if (cancelled) {
          return;
        }

        setCustomer(customerData);
        setWallet(walletData);
      } catch (error) {
        if (cancelled) {
          return;
        }

        if (
          error instanceof ApiError
          && error.status === 404
        ) {
          setError(
            "El cliente no existe.",
          );
        } else if (
          error instanceof ApiError
          && error.status === 409
        ) {
          setError(
            "El cliente no tiene un wallet disponible.",
          );
        } else {
          setError(
            "No fue posible cargar el cliente.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingCustomer(false);
        }
      }
    }

    void loadCustomer();

    return () => {
      cancelled = true;
    };
  }, [customerId]);

  useEffect(() => {
    if (!customerId) {
      return;
    }

    let cancelled = false;

    async function loadTransactions() {
      setIsLoadingTransactions(true);

      try {
        const data =
          await listCustomerTransactions(
            customerId!,
            PAGE_SIZE,
            offset,
          );

        if (!cancelled) {
          setTransactions(data);
        }
      } catch {
        if (!cancelled) {
          setError(
            "No fue posible cargar el historial de tiempo.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingTransactions(false);
        }
      }
    }

    void loadTransactions();

    return () => {
      cancelled = true;
    };
  }, [customerId, offset]);


  async function handleTimePurchase(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!customerId) {
      return;
    }

    const minutes = Number(purchaseMinutes);

    if (
      !Number.isInteger(minutes)
      || minutes <= 0
    ) {
      setPurchaseError(
        "Ingresa una cantidad de minutos mayor a cero.",
      );

      return;
    }


    const seconds = minutes * 60;

    setIsPurchasing(true);
    setPurchaseError(null);
    setPurchaseSuccess(null);

    try {
      const response =
        await purchaseCustomerTime(
          customerId,
          seconds,
        );

  
      setWallet({
        available_seconds:
          response.available_seconds,
        reserved_seconds:
          response.reserved_seconds,
      });


      const updatedTransactions =
        await listCustomerTransactions(
          customerId,
          PAGE_SIZE,
          0,
        );

      setTransactions(
        updatedTransactions,
      );

      setOffset(0);
      setPurchaseMinutes("");

      setPurchaseSuccess(
        `${minutes} min acreditados correctamente.`,
      );
    } catch (error) {
      if (
        error instanceof ApiError
        && error.status === 404
      ) {
        setPurchaseError(
          "El cliente no existe.",
        );
      } else if (
        error instanceof ApiError
        && error.status === 409
        && error.message === "Customer is inactive"
      ) {
        setPurchaseError(
          "No se puede cargar tiempo a un cliente inactivo.",
        );
      } else if (
        error instanceof ApiError
        && error.status === 409
      ) {
        setPurchaseError(
          "El cliente no tiene un wallet disponible.",
        );
      } else if (
        error instanceof ApiError
        && error.status === 422
      ) {
        setPurchaseError(
          "La cantidad de tiempo no es válida.",
        );
      } else {
        setPurchaseError(
          "No fue posible acreditar el tiempo.",
        );
      }
    } finally {
      setIsPurchasing(false);
    }
  }


  if (!customerId) {
    return (
      <section className="content-state">
        Identificador de cliente inválido.
      </section>
    );
  }

  if (isLoadingCustomer) {
    return (
      <section className="content-state">
        Cargando cliente...
      </section>
    );
  }

  if (error && !customer) {
    return (
      <section className="customer-detail-page">
        <Link
          className="back-link"
          to="/customers"
        >
          ← Volver a clientes
        </Link>

        <p className="form-error">
          {error}
        </p>
      </section>
    );
  }

  if (!customer || !wallet) {
    return null;
  }

  return (
  <section className="customer-detail-page">
    <Link
      className="back-link"
      to="/customers"
    >
      ← Volver a clientes
    </Link>

    <header className="customer-detail-header">
      <div>
        <p className="eyebrow">
          Cliente
        </p>

        <h1>
          {customer.display_name}
        </h1>

        <p className="page-description">
          @{customer.username}
        </p>
      </div>

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
    </header>

    <div className="customer-summary-grid">
      <article className="summary-card">
        <span className="summary-label">
          Tiempo disponible
        </span>

        <strong>
          {formatDuration(
            wallet.available_seconds,
          )}
        </strong>
      </article>

      <article className="summary-card">
        <span className="summary-label">
          Tiempo reservado
        </span>

        <strong>
          {formatDuration(
            wallet.reserved_seconds,
          )}
        </strong>
      </article>

      <article className="summary-card">
        <span className="summary-label">
          Registrado
        </span>

        <strong>
          {formatDateTime(
            customer.created_at,
          )}
        </strong>
      </article>
    </div>

    <section className="time-purchase-section">
      <div className="section-header">
        <div>
          <h2>
            Cargar tiempo
          </h2>

          <p className="page-description">
            Acredita minutos al saldo
            disponible del cliente.
          </p>
        </div>
      </div>

      <form
        className="time-purchase-form"
        onSubmit={handleTimePurchase}
      >
        <label className="form-field">
          <span>
            Minutos a acreditar
          </span>

          <input
            type="number"
            min="1"
            step="1"
            value={purchaseMinutes}
            onChange={(event) =>
              setPurchaseMinutes(
                event.target.value,
              )
            }
            placeholder="Ej: 60"
            disabled={isPurchasing}
          />
        </label>

        <button
          className="primary-button"
          type="submit"
          disabled={isPurchasing}
        >
          {isPurchasing
            ? "Acreditando..."
            : "Acreditar tiempo"}
        </button>
      </form>

      {purchaseError && (
        <p
          className="form-error"
          role="alert"
        >
          {purchaseError}
        </p>
      )}

      {purchaseSuccess && (
        <p
          className="form-success"
          role="status"
        >
          {purchaseSuccess}
        </p>
      )}
    </section>

    <section className="history-section">
      <div className="section-header">
        <div>
          <h2>
            Historial de tiempo
          </h2>

          <p className="page-description">
            Movimientos del wallet,
            desde el más reciente.
          </p>
        </div>
      </div>

      {error && (
        <p
          className="form-error"
          role="alert"
        >
          {error}
        </p>
      )}

      {isLoadingTransactions ? (
        <div className="content-state">
          Cargando movimientos...
        </div>
      ) : transactions.length === 0 ? (
        <div className="content-state">
          No hay movimientos
          en esta página.
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>
                  Fecha
                </th>

                <th>
                  Movimiento
                </th>

                <th>
                  Disponible
                </th>

                <th>
                  Reservado
                </th>
              </tr>
            </thead>

            <tbody>
              {transactions.map(
                (transaction) => (
                  <tr
                    key={transaction.id}
                  >
                    <td>
                      {formatDateTime(
                        transaction.created_at,
                      )}
                    </td>

                    <td>
                      {
                        transactionLabels[
                          transaction
                            .transaction_type
                        ]
                      }
                    </td>

                    <td>
                      {formatSignedDuration(
                        transaction
                          .available_seconds_delta,
                      )}
                    </td>

                    <td>
                      {formatSignedDuration(
                        transaction
                          .reserved_seconds_delta,
                      )}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="pagination">
        <button
          type="button"
          className="secondary-button"
          disabled={
            offset === 0
            || isLoadingTransactions
          }
          onClick={() =>
            setOffset(
              Math.max(
                0,
                offset - PAGE_SIZE,
              ),
            )
          }
        >
          Anterior
        </button>

        <span>
          Página{" "}
          {Math.floor(
            offset / PAGE_SIZE,
          ) + 1}
        </span>

        <button
          type="button"
          className="secondary-button"
          disabled={
            transactions.length
              < PAGE_SIZE
            || isLoadingTransactions
          }
          onClick={() =>
            setOffset(
              offset + PAGE_SIZE,
            )
          }
        >
          Siguiente
        </button>
      </div>
    </section>
  </section>
);
}