from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


StationStatus = Literal[
    "AVAILABLE",
    "IN_USE",
    "MAINTENANCE",
    "OFFLINE",
]


class StationCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    code: str = Field(
        min_length=1,
        max_length=50,
    )


class StationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    code: str
    status: StationStatus
    created_at: datetime
    updated_at: datetime