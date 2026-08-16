from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.station import Station
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession
from app.models.user import User


def _calculate_elapsed_seconds(
    *,
    started_at: datetime,
    ended_at: datetime,
    authorized_seconds: int,
) -> int:
    delta = ended_at - started_at

    elapsed_microseconds = (
        delta.days * 86_400_000_000
        + delta.seconds * 1_000_000
        + delta.microseconds
    )

    if elapsed_microseconds <= 0:
        return 0

    elapsed_seconds = (
        elapsed_microseconds
        // 1_000_000
    )

    return min(
        elapsed_seconds,
        authorized_seconds,
    )


class UsageSessionNotFoundError(Exception):
    pass


class UsageSessionAlreadyFinishedError(Exception):
    pass


class SessionReservationMismatchError(Exception):
    pass


class SessionFinishConflictError(Exception):
    pass


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


class InvalidAdditionalTimeError(Exception):
    pass


class SessionExtensionConflictError(Exception):
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
    
    
@dataclass(frozen=True)
class SessionFinishResult:
    session_id: UUID
    station_id: UUID
    customer_id: UUID
    authorized_seconds: int
    consumed_seconds: int
    released_seconds: int
    available_seconds: int
    reserved_seconds: int
    session_status: str
    station_status: str
    started_at: datetime
    ended_at: datetime


@dataclass(frozen=True)
class ActiveSessionResult:
    session_id: UUID
    station_id: UUID
    station_code: str
    customer_id: UUID
    customer_username: str
    customer_display_name: str
    authorized_seconds: int
    started_at: datetime
    elapsed_seconds: int
    remaining_seconds: int

 
def finish_registered_customer_session(
    db: Session,
    *,
    session_id: UUID,
    actor_user_id: UUID,
) -> SessionFinishResult:
    try:
        session_station_id = db.scalar(
            select(UsageSession.station_id).where(
                UsageSession.id == session_id
        ))

        if session_station_id is None:
            raise UsageSessionNotFoundError
        
        ended_at = db.scalar(
                    select(
                        func.clock_timestamp()
                    )
                )
        
        if ended_at is None:
                    raise SessionFinishConflictError
        
        station = db.scalar(
            select(Station)
            .where(
                Station.id == session_station_id
            )
            .with_for_update()
        )

        if station is None:
            raise SessionStationNotFoundError

        usage_session = db.scalar(
            select(UsageSession)
            .where(
                UsageSession.id == session_id
            )
            .with_for_update()
        )

        if usage_session is None:
            raise UsageSessionNotFoundError

        if usage_session.status != "ACTIVE":
            raise UsageSessionAlreadyFinishedError

        wallet = db.scalar(
            select(TimeWallet)
            .where(
                TimeWallet.user_id
                == usage_session.user_id
            )
            .with_for_update()
        )

        if wallet is None:
            raise SessionWalletNotFoundError

        if (
            wallet.reserved_seconds
            < usage_session.authorized_seconds
        ):
            raise SessionReservationMismatchError

        
        consumed_seconds = (
            _calculate_elapsed_seconds(
                started_at=usage_session.started_at,
                ended_at=ended_at,
                authorized_seconds=(
                    usage_session.authorized_seconds
                    ),
                ))

        released_seconds = (
            usage_session.authorized_seconds
            - consumed_seconds
        )

        wallet.reserved_seconds -= (
            usage_session.authorized_seconds
        )

        wallet.available_seconds += (
            released_seconds
        )

        transactions: list[
            TimeTransaction
        ] = []

        if consumed_seconds > 0:
            transactions.append(
                TimeTransaction(
                    wallet_id=wallet.id,
                    transaction_type=(
                        "SESSION_USAGE"
                    ),
                    available_seconds_delta=0,
                    reserved_seconds_delta=(
                        -consumed_seconds
                    ),
                    actor_user_id=actor_user_id,
                )
            )

        if released_seconds > 0:
            transactions.append(
                TimeTransaction(
                    wallet_id=wallet.id,
                    transaction_type=(
                        "SESSION_RELEASE"
                    ),
                    available_seconds_delta=(
                        released_seconds
                    ),
                    reserved_seconds_delta=(
                        -released_seconds
                    ),
                    actor_user_id=actor_user_id,
                )
            )

        usage_session.status = "FINISHED"
        usage_session.consumed_seconds = (
            consumed_seconds
        )
        usage_session.ended_at = ended_at

        station.status = "AVAILABLE"

        db.add_all(transactions)

        db.flush()

        result = SessionFinishResult(
            session_id=usage_session.id,
            station_id=station.id,
            customer_id=usage_session.user_id,
            authorized_seconds=(
                usage_session.authorized_seconds
            ),
            consumed_seconds=consumed_seconds,
            released_seconds=released_seconds,
            available_seconds=(
                wallet.available_seconds
            ),
            reserved_seconds=(
                wallet.reserved_seconds
            ),
            session_status=usage_session.status,
            station_status=station.status,
            started_at=usage_session.started_at,
            ended_at=ended_at,
        )

        db.commit()

        return result

    except IntegrityError as exc:
        db.rollback()
        raise SessionFinishConflictError from exc

    except Exception:
        db.rollback()
        raise


def list_active_registered_customer_sessions(
    db: Session,
) -> list[ActiveSessionResult]:
    server_now = db.scalar(
        select(
            func.clock_timestamp()
        )
    )

    if server_now is None:
        return []

    rows = db.execute(
        select(
            UsageSession,
            Station.code,
            User.username,
            User.display_name,
        )
        .join(
            Station,
            Station.id
            == UsageSession.station_id,
        )
        .join(
            User,
            User.id
            == UsageSession.user_id,
        )
        .where(
            UsageSession.status == "ACTIVE"
        )
        .order_by(
            Station.code,
            UsageSession.started_at,
        )
    ).all()

    results: list[
        ActiveSessionResult
    ] = []

    for (
        usage_session,
        station_code,
        customer_username,
        customer_display_name,
    ) in rows:
        elapsed_seconds = (
            _calculate_elapsed_seconds(
                started_at=usage_session.started_at,
                ended_at=server_now,
                authorized_seconds=(
                    usage_session.authorized_seconds
                ),
            )
        )

        remaining_seconds = (
            usage_session.authorized_seconds
            - elapsed_seconds
        )

        results.append(
            ActiveSessionResult(
                session_id=usage_session.id,
                station_id=(
                    usage_session.station_id
                ),
                station_code=station_code,
                customer_id=(
                    usage_session.user_id
                ),
                customer_username=(
                    customer_username
                ),
                customer_display_name=(
                    customer_display_name
                ),
                authorized_seconds=(
                    usage_session.authorized_seconds
                ),
                started_at=(
                    usage_session.started_at
                ),
                elapsed_seconds=(
                    elapsed_seconds
                ),
                remaining_seconds=(
                    remaining_seconds
                ),
            )
        )

    return results


@dataclass(frozen=True)
class SessionExtensionResult:
    session_id: UUID
    station_id: UUID
    customer_id: UUID
    additional_seconds: int
    authorized_seconds: int
    available_seconds: int
    reserved_seconds: int
    session_status: str
    started_at: datetime


def extend_registered_customer_session(
    db: Session,
    *,
    session_id: UUID,
    additional_seconds: int,
    actor_user_id: UUID,
) -> SessionExtensionResult:
    if additional_seconds <= 0:
        raise InvalidAdditionalTimeError

    try:
        usage_session = db.scalar(
            select(UsageSession)
            .where(
                UsageSession.id == session_id
            )
            .with_for_update()
        )

        if usage_session is None:
            raise UsageSessionNotFoundError

        if usage_session.status != "ACTIVE":
            raise UsageSessionAlreadyFinishedError

        wallet = db.scalar(
            select(TimeWallet)
            .where(
                TimeWallet.user_id
                == usage_session.user_id
            )
            .with_for_update()
        )

        if wallet is None:
            raise SessionWalletNotFoundError

        if (
            wallet.available_seconds
            < additional_seconds
        ):
            raise InsufficientTimeBalanceError

        wallet.available_seconds -= (
            additional_seconds
        )

        wallet.reserved_seconds += (
            additional_seconds
        )

        usage_session.authorized_seconds += (
            additional_seconds
        )

        transaction = TimeTransaction(
            wallet_id=wallet.id,
            transaction_type="SESSION_RESERVE",
            available_seconds_delta=(
                -additional_seconds
            ),
            reserved_seconds_delta=(
                additional_seconds
            ),
            actor_user_id=actor_user_id,
        )

        db.add(transaction)

        db.flush()

        result = SessionExtensionResult(
            session_id=usage_session.id,
            station_id=usage_session.station_id,
            customer_id=usage_session.user_id,
            additional_seconds=(
                additional_seconds
            ),
            authorized_seconds=(
                usage_session.authorized_seconds
            ),
            available_seconds=(
                wallet.available_seconds
            ),
            reserved_seconds=(
                wallet.reserved_seconds
            ),
            session_status=(
                usage_session.status
            ),
            started_at=(
                usage_session.started_at
            ),
        )

        db.commit()

        return result

    except IntegrityError as exc:
        db.rollback()
        raise SessionExtensionConflictError from exc

    except Exception:
        db.rollback()
        raise