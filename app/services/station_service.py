from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.station import Station


class InvalidStationCodeError(Exception):
    pass


class StationAlreadyExistsError(Exception):
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