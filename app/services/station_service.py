from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID
from app.models.station import Station
from app.models.usage_session import UsageSession

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