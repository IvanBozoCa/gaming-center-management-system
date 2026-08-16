from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class AdminCustomerSummaryResponse(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    username: str
    display_name: str
    is_active: bool
    created_at: datetime

    available_seconds: int = Field(
        ge=0,
    )

    reserved_seconds: int = Field(
        ge=0,
    )