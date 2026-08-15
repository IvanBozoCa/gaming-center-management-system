from pydantic import BaseModel, ConfigDict, Field


class TimeWalletResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    available_seconds: int = Field(
        ge=0
    )

    reserved_seconds: int = Field(
        ge=0
    )