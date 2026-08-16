from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class TimePurchaseCreate(BaseModel):
    seconds: int = Field(
        gt=0,
    )


class TimePurchaseResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    transaction_id: UUID
    customer_id: UUID
    credited_seconds: int = Field(
        gt=0
    )

    available_seconds: int = Field(
        ge=0
    )

    reserved_seconds: int = Field(
        ge=0
    )

    transaction_type: str
    created_at: datetime