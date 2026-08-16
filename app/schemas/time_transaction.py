from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
)


class TimeTransactionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    transaction_type: Literal[
        "PURCHASE",
        "SESSION_RESERVE",
        "SESSION_USAGE",
        "SESSION_RELEASE",
        "BONUS",
        "ADJUSTMENT",
        "REFUND",
    ]

    available_seconds_delta: int
    reserved_seconds_delta: int

    actor_user_id: UUID | None
    created_at: datetime