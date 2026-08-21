from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Literal
from uuid import UUID, uuid4

from fastapi import WebSocket


StationConnectionStatus = Literal[
    "CONNECTED",
    "OFFLINE",
]


@dataclass(frozen=True)
class StationPresenceSnapshot:
    connection_status: (
        StationConnectionStatus
    )

    connected_at: datetime | None
    last_heartbeat_at: datetime | None


@dataclass
class StationConnection:
    connection_id: UUID
    websocket: WebSocket
    connected_at: datetime
    last_heartbeat_at: datetime


class StationPresenceRegistry:
    def __init__(self) -> None:
        self._connections: dict[
            UUID,
            StationConnection,
        ] = {}

        self._lock = Lock()

    def register(
        self,
        station_id: UUID,
        websocket: WebSocket,
    ) -> tuple[
        StationConnection,
        WebSocket | None,
    ]:
        server_now = datetime.now(
            timezone.utc
        )

        connection = StationConnection(
            connection_id=uuid4(),
            websocket=websocket,
            connected_at=server_now,
            last_heartbeat_at=server_now,
        )

        with self._lock:
            previous = self._connections.get(
                station_id
            )

            self._connections[
                station_id
            ] = connection

        previous_websocket = (
            previous.websocket
            if previous is not None
            else None
        )

        return (
            connection,
            previous_websocket,
        )

    def record_heartbeat(
        self,
        station_id: UUID,
        connection_id: UUID,
    ) -> datetime | None:
        server_now = datetime.now(
            timezone.utc
        )

        with self._lock:
            connection = (
                self._connections.get(
                    station_id
                )
            )

            if (
                connection is None
                or connection.connection_id
                != connection_id
            ):
                return None

            connection.last_heartbeat_at = (
                server_now
            )

        return server_now

    def unregister(
        self,
        station_id: UUID,
        connection_id: UUID,
    ) -> None:
        with self._lock:
            connection = (
                self._connections.get(
                    station_id
                )
            )

            if (
                connection is not None
                and connection.connection_id
                == connection_id
            ):
                self._connections.pop(
                    station_id,
                    None,
                )

    def get_presence(
        self,
        station_id: UUID,
    ) -> StationPresenceSnapshot:
        with self._lock:
            connection = (
                self._connections.get(
                    station_id
                )
            )

            if connection is None:
                return StationPresenceSnapshot(
                    connection_status=(
                        "OFFLINE"
                    ),
                    connected_at=None,
                    last_heartbeat_at=None,
                )

            return StationPresenceSnapshot(
                connection_status=(
                    "CONNECTED"
                ),
                connected_at=(
                    connection.connected_at
                ),
                last_heartbeat_at=(
                    connection
                    .last_heartbeat_at
                ),
            )


station_presence_registry = (
    StationPresenceRegistry()
)