from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID
from app.models.station import Station
from app.models.usage_session import UsageSession
from app.core.agent_security import (
    generate_agent_credential,
    hash_agent_secret,
    parse_agent_token,
    verify_agent_secret,
)

ADMIN_MANAGED_STATION_STATUSES = frozenset(
    {
        "AVAILABLE",
        "MAINTENANCE",
        "OFFLINE",
    }
)


class InvalidStationCodeError(Exception):
    pass


class StationAlreadyExistsError(Exception):
    pass


class StationNotFoundError(Exception):
    pass


class InvalidStationStatusError(Exception):
    pass


class StationInUseError(Exception):
    pass


def normalize_station_code(
    code: str,
) -> str:
    normalized_code = code.strip().upper()

    if (
        not normalized_code
        or len(normalized_code) > 50
    ):
        raise InvalidStationCodeError

    return normalized_code


def create_station(
    db: Session,
    *,
    code: str,
) -> Station:
    normalized_code = normalize_station_code(
        code
    )

    existing_station = db.scalar(
        select(Station).where(
            Station.code == normalized_code
        )
    )

    if existing_station is not None:
        raise StationAlreadyExistsError

    station = Station(
        code=normalized_code,
        status="AVAILABLE",
    )

    db.add(station)

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()
        raise StationAlreadyExistsError from exc

    except Exception:
        db.rollback()
        raise

    db.refresh(station)

    return station


def list_stations(
    db: Session,
) -> list[Station]:
    return list(
        db.scalars(
            select(Station).order_by(
                Station.code
            )
        ).all()
    )


def update_station_status(
    db: Session,
    *,
    station_id: UUID,
    status: str,
) -> Station:
    if status not in (
        ADMIN_MANAGED_STATION_STATUSES
    ):
        raise InvalidStationStatusError

    try:
        station = db.scalar(
            select(Station)
            .where(
                Station.id == station_id
            )
            .with_for_update()
        )

        if station is None:
            raise StationNotFoundError

        active_session_id = db.scalar(
            select(UsageSession.id)
            .where(
                UsageSession.station_id
                == station.id,
                UsageSession.status
                == "ACTIVE",
            )
            .limit(1)
        )

        if (
            station.status == "IN_USE"
            or active_session_id is not None
        ):
            raise StationInUseError

        if station.status == status:
            db.commit()
            db.refresh(station)

            return station

        station.status = status

        db.commit()
        db.refresh(station)

        return station

    except Exception:
        db.rollback()
        raise

@dataclass(frozen=True)
class AgentCredentialResult:
    station_id: UUID
    station_code: str
    agent_token: str


def rotate_station_agent_credential(
    db: Session,
    *,
    station_id: UUID,
) -> AgentCredentialResult:
    try:
        station = db.scalar(
            select(Station)
            .where(
                Station.id
                == station_id
            )
            .with_for_update()
        )

        if station is None:
            raise StationNotFoundError

        (
            key_id,
            secret,
            token,
        ) = generate_agent_credential()

        station.agent_key_id = (
            key_id
        )

        station.agent_secret_hash = (
            hash_agent_secret(secret)
        )

        db.commit()
        db.refresh(station)

        return AgentCredentialResult(
            station_id=station.id,
            station_code=station.code,
            agent_token=token,
        )

    except Exception:
        db.rollback()
        raise


def authenticate_station_agent(
    db: Session,
    *,
    token: str,
) -> Station | None:
    parsed = parse_agent_token(
        token
    )

    if parsed is None:
        return None

    key_id, secret = parsed

    station = db.scalar(
        select(Station).where(
            Station.agent_key_id
            == key_id
        )
    )

    if (
        station is None
        or station.agent_secret_hash
        is None
    ):
        return None

    if not verify_agent_secret(
        secret,
        station.agent_secret_hash,
    ):
        return None

    return station


def record_station_heartbeat(
    db: Session,
    *,
    station_id: UUID,
) -> Station:
    try:
        station = db.scalar(
            select(Station)
            .where(
                Station.id
                == station_id
            )
            .with_for_update()
        )

        if station is None:
            raise StationNotFoundError

        server_now = db.scalar(
            select(
                func.clock_timestamp()
            )
        )

        if server_now is None:
            raise RuntimeError(
                "Unable to obtain server time"
            )

        station.last_seen_at = (
            server_now
        )

        db.commit()
        db.refresh(station)

        return station

    except Exception:
        db.rollback()
        raise