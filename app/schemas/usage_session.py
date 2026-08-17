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


class ActiveSessionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    session_id: UUID

    station_id: UUID
    station_code: str

    customer_id: UUID
    customer_username: str
    customer_display_name: str

    authorized_seconds: int = Field(
        gt=0,
    )
    started_at: datetime

    elapsed_seconds: int = Field(
        ge=0,
    )
    remaining_seconds: int = Field(
        ge=0,
    )
    time_state: Literal[
        "RUNNING",
        "EXHAUSTED",
    ]


class FinishedSessionHistoryResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    session_id: UUID

    station_id: UUID
    station_code: str

    customer_id: UUID
    customer_username: str
    customer_display_name: str

    authorized_seconds: int = Field(
        gt=0,
    )
    consumed_seconds: int = Field(
        ge=0,
    )
    released_seconds: int = Field(
        ge=0,
    )

    started_at: datetime
    ended_at: datetime


class SessionExtensionCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    additional_seconds: int = Field(
        gt=0,
    )


class SessionExtensionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    session_id: UUID
    station_id: UUID
    customer_id: UUID

    additional_seconds: int = Field(
        gt=0,
    )
    authorized_seconds: int = Field(
        gt=0,
    )

    available_seconds: int = Field(
        ge=0,
    )
    reserved_seconds: int = Field(
        ge=0,
    )

    session_status: Literal["ACTIVE"]

    started_at: datetime
    

class GuestSessionStartCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    station_id: UUID

    authorized_seconds: int = Field(
        gt=0,
    )


class GuestSessionStartResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    session_id: UUID
    station_id: UUID

    authorized_seconds: int = Field(
        gt=0,
    )

    session_type: Literal["GUEST"]
    session_status: Literal["ACTIVE"]
    station_status: Literal["IN_USE"]

    started_at: datetime
    

class ActiveGuestSessionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    session_id: UUID

    station_id: UUID
    station_code: str

    authorized_seconds: int = Field(
        gt=0,
    )
    started_at: datetime

    elapsed_seconds: int = Field(
        ge=0,
    )
    remaining_seconds: int = Field(
        ge=0,
    )

    time_state: Literal[
        "RUNNING",
        "EXHAUSTED",
    ]