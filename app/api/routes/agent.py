import asyncio

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_station_agent,
    get_db,
)
from app.core.config import settings
from app.models.station import Station
from app.schemas.agent_protocol import (
    AgentHeartbeatMessage,
    ServerAgentMessage,
)
from app.schemas.station import (
    StationAgentResponse,
)
from app.services.station_service import (
    authenticate_station_agent,
    record_station_heartbeat,
)
from app.services.station_presence import (
    station_presence_registry,
)


router = APIRouter(
    prefix="/agent",
    tags=["Station Agent"],
)


@router.get(
    "/station",
    response_model=StationAgentResponse,
)
def get_agent_station(
    station: Station = Depends(
        get_current_station_agent
    ),
):
    return station


@router.post(
    "/heartbeat",
    response_model=StationAgentResponse,
)
def heartbeat(
    db: Session = Depends(get_db),
    station: Station = Depends(
        get_current_station_agent
    ),
):
    return record_station_heartbeat(
        db,
        station_id=station.id,
    )


def authenticate_websocket_station(
    websocket: WebSocket,
    db: Session,
) -> Station:
    authorization = websocket.headers.get(
        "authorization"
    )

    if authorization is None:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Station agent authentication required",
        )

    scheme, separator, token = (
        authorization.partition(" ")
    )

    if (
        not separator
        or scheme.lower() != "bearer"
        or not token.strip()
    ):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid station agent credentials",
        )

    station = authenticate_station_agent(
        db,
        token=token.strip(),
    )

    if station is None:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid station agent credentials",
        )

    return station


async def send_agent_message(
    websocket: WebSocket,
    message: ServerAgentMessage,
) -> None:
    await websocket.send_json(
        message.model_dump(
            mode="json",
        )
    )


@router.websocket("/ws")
async def station_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    station = authenticate_websocket_station(
        websocket,
        db,
    )

    await websocket.accept()

    connection, _ = (
    station_presence_registry.register(
        station.id,
        websocket,
    )
)

    await send_agent_message(
        websocket,
        ServerAgentMessage(
            type="CONNECTED",
            data={
                "station_id": str(station.id),
                "station_code": station.code,
                "heartbeat_interval_seconds": (
                    settings
                    .agent_heartbeat_interval_seconds
                ),
            },
        ),
    )

    try:
        while True:
            try:
                incoming = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=(
                        settings
                        .agent_heartbeat_timeout_seconds
                    ),
                )

            except TimeoutError:
                await websocket.close(
                    code=(
                        status
                        .WS_1008_POLICY_VIOLATION
                    ),
                    reason="Heartbeat timeout",
                )
                return

            if (
                incoming["type"]
                == "websocket.disconnect"
            ):
                return

            raw_message = incoming.get("text")

            if raw_message is None:
                await websocket.close(
                    code=(
                        status
                        .WS_1003_UNSUPPORTED_DATA
                    ),
                    reason="Text messages required",
                )
                return

            message_size = len(
                raw_message.encode("utf-8")
            )

            if (
                message_size
                > settings
                .agent_websocket_max_message_bytes
            ):
                await websocket.close(
                    code=(
                        status
                        .WS_1009_MESSAGE_TOO_BIG
                    ),
                    reason="Message too large",
                )
                return

            try:
                message = (
                    AgentHeartbeatMessage
                    .model_validate_json(
                        raw_message
                    )
                )

            except (
                ValidationError,
                ValueError,
            ):
                await send_agent_message(
                    websocket,
                    ServerAgentMessage(
                        type="ERROR",
                        data={
                            "code": (
                                "INVALID_MESSAGE"
                            ),
                        },
                    ),
                )
                continue
            

            heartbeat_at = (
                station_presence_registry
                .record_heartbeat(
                    station.id,
                    connection.connection_id,
                )
            )

            if heartbeat_at is None:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Station connection superseded",
                )
                return
            
            updated_station = (
                record_station_heartbeat(
                    db,
                    station_id=station.id,
                )
            )

            await send_agent_message(
                websocket,
                ServerAgentMessage(
                    type="HEARTBEAT_ACK",
                    correlation_id=(
                        message.event_id
                    ),
                    data={
                        "station_id": str(
                            updated_station.id
                        ),
                        "last_seen_at": (
                            updated_station
                            .last_seen_at
                        ),
                    },
                ),
            )

    except WebSocketDisconnect:
        return
    
    finally:
        station_presence_registry.unregister(
            station.id,
            connection.connection_id,
        )