from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.time_wallet import TimeWallet


class TimeTransaction(Base):
    __tablename__ = "time_transactions"

    __table_args__ = (
        CheckConstraint(
            """
            transaction_type IN (
                'PURCHASE',
                'SESSION_RESERVE',
                'SESSION_USAGE',
                'SESSION_RELEASE',
                'BONUS',
                'ADJUSTMENT',
                'REFUND'
            )
            """,
            name="ck_time_transactions_type",
        ),
        CheckConstraint(
            """
            available_seconds_delta <> 0
            OR reserved_seconds_delta <> 0
            """,
            name="ck_time_transactions_non_zero_delta",
        ),
        Index(
            "ix_time_transactions_wallet_created_at",
            "wallet_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    wallet_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "time_wallets.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    available_seconds_delta: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    reserved_seconds_delta: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    wallet: Mapped["TimeWallet"] = relationship(
        back_populates="transactions",
    )