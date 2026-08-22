import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.agent_protocol import (
    ServerAgentMessage,
)
from app.services.station_presence import (
    station_presence_registry,
)
from app.services.station_session_sync import (
    get_active_station_session_snapshot,
)


logger = logging.getLogger(__name__)


ActiveSessionEventType = Literal[
    "SESSION_START",
    "SESSION_EXTEND",
]


def publish_active_session_event(
    db: Session,
    *,
    station_id: UUID,
    session_id: UUID,
    event_type: ActiveSessionEventType,
) -> bool:
    try:
        snapshot = (
            get_active_station_session_snapshot(
                db,
                station_id=station_id,
            )
        )

        if (
            snapshot is None
            or snapshot.session_id
            != session_id
        ):
            return False

        message = ServerAgentMessage(
            type=event_type,
            data={
                "session_id": str(
                    snapshot.session_id
                ),
                "session_type": (
                    snapshot.session_type
                ),
                "authorized_seconds": (
                    snapshot
                    .authorized_seconds
                ),
                "started_at": (
                    snapshot.started_at
                ),
                "server_now": (
                    snapshot.server_now
                ),
                "elapsed_seconds": (
                    snapshot.elapsed_seconds
                ),
                "remaining_seconds": (
                    snapshot
                    .remaining_seconds
                ),
                "time_state": (
                    snapshot.time_state
                ),
            },
        )

        return (
            station_presence_registry.publish(
                station_id,
                message.model_dump(
                    mode="json"
                ),
            )
        )

    except Exception:
        logger.warning(
            "Could not publish active "
            "station session event.",
            exc_info=True,
        )

        return False


def publish_session_finish_event(
    *,
    station_id: UUID,
    session_id: UUID,
    session_type: Literal[
        "REGISTERED",
        "GUEST",
    ],
    ended_at: datetime,
) -> bool:
    message = ServerAgentMessage(
        type="SESSION_FINISH",
        data={
            "session_id": str(
                session_id
            ),
            "session_type": (
                session_type
            ),
            "ended_at": ended_at,
        },
    )

    return station_presence_registry.publish(
        station_id,
        message.model_dump(
            mode="json"
        ),
    )