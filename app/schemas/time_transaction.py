from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
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

    available_seconds_delta: int = Field(
        description=(
            "Cambio aplicado al saldo de tiempo "
            "disponible, expresado en segundos. "
            "Un valor positivo agrega tiempo y "
            "un valor negativo lo descuenta."
        ),
    )

    reserved_seconds_delta: int = Field(
        description=(
            "Cambio aplicado al tiempo reservado "
            "para sesiones, expresado en segundos. "
            "Un valor positivo reserva tiempo y "
            "un valor negativo libera o consume "
            "tiempo reservado."
        ),
    )

    actor_user_id: UUID | None = Field(
        description=(
            "Usuario que originó el movimiento "
            "cuando existe un actor identificable."
        ),
    )

    created_at: datetime = Field(
        description=(
            "Fecha y hora en que el movimiento "
            "fue registrado."
        ),
    )

