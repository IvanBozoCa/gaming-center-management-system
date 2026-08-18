from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class TimeProductCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    duration_seconds: int = Field(
        gt=0,
    )

    price_clp: int = Field(
        ge=0,
    )


class TimeProductUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    duration_seconds: int | None = Field(
        default=None,
        gt=0,
    )

    price_clp: int | None = Field(
        default=None,
        ge=0,
    )

    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError(
                "At least one field must be provided"
            )

        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(
                    f"{field_name} cannot be null"
                )

        return self


class TimeProductResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    name: str
    duration_seconds: int
    price_clp: int
    is_active: bool
    created_at: datetime
    updated_at: datetime