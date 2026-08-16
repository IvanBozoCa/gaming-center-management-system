from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.station import Station
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession
from app.models.user import User


class InvalidAuthorizedTimeError(Exception):
    pass


class SessionStationNotFoundError(Exception):
    pass


class SessionStationUnavailableError(Exception):
    pass


class SessionCustomerNotFoundError(Exception):
    pass


class SessionInactiveCustomerError(Exception):
    pass


class SessionWalletNotFoundError(Exception):
    pass


class InsufficientTimeBalanceError(Exception):
    pass


class StationActiveSessionError(Exception):
    pass


class CustomerActiveSessionError(Exception):
    pass


class SessionStartConflictError(Exception):
    pass


@dataclass(frozen=True)
class SessionStartResult:
    session_id: UUID
    station_id: UUID
    customer_id: UUID
    authorized_seconds: int
    available_seconds: int
    reserved_seconds: int
    station_status: str
    started_at: datetime


def start_registered_customer_session(
    db: Session,
    *,
    station_id: UUID,
    customer_id: UUID,
    authorized_seconds: int,
    actor_user_id: UUID,
) -> SessionStartResult:
    if authorized_seconds <= 0:
        raise InvalidAuthorizedTimeError

    try:
        station = db.scalar(
            select(Station)
            .where(
                Station.id == station_id
            )
            .with_for_update()
        )

        if station is None:
            raise SessionStationNotFoundError

        if station.status != "AVAILABLE":
            raise SessionStationUnavailableError

        customer = db.scalar(
            select(User)
            .where(
                User.id == customer_id
            )
            .with_for_update()
        )

        if (
            customer is None
            or customer.role != "CUSTOMER"
        ):
            raise SessionCustomerNotFoundError

        if not customer.is_active:
            raise SessionInactiveCustomerError

        wallet = db.scalar(
            select(TimeWallet)
            .where(
                TimeWallet.user_id == customer.id
            )
            .with_for_update()
        )

        if wallet is None:
            raise SessionWalletNotFoundError

        if (
            wallet.available_seconds
            < authorized_seconds
        ):
            raise InsufficientTimeBalanceError

        active_station_session = db.scalar(
            select(UsageSession).where(
                UsageSession.station_id
                == station.id,
                UsageSession.status
                == "ACTIVE",
            )
        )

        if active_station_session is not None:
            raise StationActiveSessionError

        active_customer_session = db.scalar(
            select(UsageSession).where(
                UsageSession.user_id
                == customer.id,
                UsageSession.status
                == "ACTIVE",
            )
        )

        if active_customer_session is not None:
            raise CustomerActiveSessionError

        wallet.available_seconds -= (
            authorized_seconds
        )
        wallet.reserved_seconds += (
            authorized_seconds
        )

        transaction = TimeTransaction(
            wallet_id=wallet.id,
            transaction_type="SESSION_RESERVE",
            available_seconds_delta=(
                -authorized_seconds
            ),
            reserved_seconds_delta=(
                authorized_seconds
            ),
            actor_user_id=actor_user_id,
        )

        usage_session = UsageSession(
            station_id=station.id,
            user_id=customer.id,
            status="ACTIVE",
            authorized_seconds=(
                authorized_seconds
            ),
        )

        station.status = "IN_USE"

        db.add_all(
            [
                transaction,
                usage_session,
            ]
        )

        db.flush()
        db.refresh(usage_session)

        result = SessionStartResult(
            session_id=usage_session.id,
            station_id=station.id,
            customer_id=customer.id,
            authorized_seconds=(
                authorized_seconds
            ),
            available_seconds=(
                wallet.available_seconds
            ),
            reserved_seconds=(
                wallet.reserved_seconds
            ),
            station_status=station.status,
            started_at=usage_session.started_at,
        )

        db.commit()

        return result

    except IntegrityError as exc:
        db.rollback()
        raise SessionStartConflictError from exc

    except Exception:
        db.rollback()
        raise