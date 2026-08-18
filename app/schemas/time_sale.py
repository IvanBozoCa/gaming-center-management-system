from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class RegisteredTimeSaleCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    sale_type: Literal["REGISTERED"]
    time_product_id: UUID
    customer_id: UUID


class GuestTimeSaleCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    sale_type: Literal["GUEST"]
    time_product_id: UUID
    station_id: UUID


TimeSaleCreate = Annotated[
    RegisteredTimeSaleCreate
    | GuestTimeSaleCreate,
    Field(discriminator="sale_type"),
]


class RegisteredTimeSaleResponse(BaseModel):
    sale_id: UUID
    sale_type: Literal["REGISTERED"]

    time_product_id: UUID
    product_name: str
    duration_seconds: int
    price_clp: int

    customer_id: UUID
    time_transaction_id: UUID

    available_seconds: int
    reserved_seconds: int

    created_at: datetime


class GuestTimeSaleResponse(BaseModel):
    sale_id: UUID
    sale_type: Literal["GUEST"]

    time_product_id: UUID
    product_name: str
    duration_seconds: int
    price_clp: int

    station_id: UUID
    usage_session_id: UUID

    session_status: str
    station_status: str

    started_at: datetime
    created_at: datetime


TimeSaleResponse = Annotated[
    RegisteredTimeSaleResponse
    | GuestTimeSaleResponse,
    Field(discriminator="sale_type"),
]