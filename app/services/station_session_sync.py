from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.usage_session import UsageSession


@dataclass(frozen=True)
class StationSessionSnapshot:
    session_id: UUID
    session_type: str

    authorized_seconds: int

    started_at: datetime
    server_now: datetime

    elapsed_seconds: int
    remaining_seconds: int

    time_state: str


def get_active_station_session_snapshot(
    db: Session,
    *,
    station_id: UUID,
) -> StationSessionSnapshot | None:
    server_now = db.scalar(
        select(
            func.clock_timestamp()
        )
    )

    if server_now is None:
        return None

    usage_session = db.scalar(
        select(UsageSession)
        .where(
            UsageSession.station_id
            == station_id,
            UsageSession.status
            == "ACTIVE",
        )
        .limit(1)
    )

    if usage_session is None:
        return None

    delta = (
        server_now
        - usage_session.started_at
    )

    elapsed_seconds = max(
        0,
        int(delta.total_seconds()),
    )

    elapsed_seconds = min(
        elapsed_seconds,
        usage_session.authorized_seconds,
    )

    remaining_seconds = (
        usage_session.authorized_seconds
        - elapsed_seconds
    )

    time_state = (
        "RUNNING"
        if remaining_seconds > 0
        else "EXHAUSTED"
    )

    return StationSessionSnapshot(
        session_id=usage_session.id,
        session_type=(
            usage_session.session_type
        ),
        authorized_seconds=(
            usage_session.authorized_seconds
        ),
        started_at=(
            usage_session.started_at
        ),
        server_now=server_now,
        elapsed_seconds=elapsed_seconds,
        remaining_seconds=(
            remaining_seconds
        ),
        time_state=time_state,
    )