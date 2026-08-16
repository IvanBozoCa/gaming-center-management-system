from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class SessionStartCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    station_id: UUID
    customer_id: UUID
    authorized_seconds: int = Field(
        gt=0,
    )


class SessionStartResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    session_id: UUID
    station_id: UUID
    customer_id: UUID
    authorized_seconds: int = Field(
        gt=0,
    )
    available_seconds: int = Field(
        ge=0,
    )
    reserved_seconds: int = Field(
        ge=0,
    )
    station_status: Literal["IN_USE"]
    started_at: datetime
    
class SessionFinishResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    session_id: UUID
    station_id: UUID
    customer_id: UUID

    authorized_seconds: int = Field(
        gt=0,
    )
    consumed_seconds: int = Field(
        ge=0,
    )
    released_seconds: int = Field(
        ge=0,
    )

    available_seconds: int = Field(
        ge=0,
    )
    reserved_seconds: int = Field(
        ge=0,
    )

    session_status: Literal["FINISHED"]
    station_status: Literal["AVAILABLE"]

    started_at: datetime
    ended_at: datetime