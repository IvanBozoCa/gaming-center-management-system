from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class AgentHeartbeatMessage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    version: Literal[1]
    type: Literal["HEARTBEAT"]
    event_id: UUID
    correlation_id: UUID | None = None
    sent_at: datetime


class ServerAgentMessage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    version: Literal[1] = 1

    type: Literal[
        "CONNECTED",
        "HEARTBEAT_ACK",
        "SESSION_START",
        "SESSION_EXTEND",
        "SESSION_FINISH",
        "ERROR",
    ]

    event_id: UUID = Field(
        default_factory=uuid4,
    )

    correlation_id: UUID | None = None

    sent_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    data: dict[str, Any] = Field(
        default_factory=dict,
    )