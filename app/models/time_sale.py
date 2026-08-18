from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TimeSale(Base):
    __tablename__ = "time_sales"

    __table_args__ = (
        CheckConstraint(
            """
            sale_type IN (
                'REGISTERED',
                'GUEST'
            )
            """,
            name="ck_time_sales_type",
        ),
        CheckConstraint(
            "duration_seconds > 0",
            name="ck_time_sales_duration_positive",
        ),
        CheckConstraint(
            "price_clp >= 0",
            name="ck_time_sales_price_non_negative",
        ),
        CheckConstraint(
            """
            (
                sale_type = 'REGISTERED'
                AND customer_id IS NOT NULL
                AND station_id IS NULL
                AND time_transaction_id IS NOT NULL
                AND usage_session_id IS NULL
            )
            OR
            (
                sale_type = 'GUEST'
                AND customer_id IS NULL
                AND station_id IS NOT NULL
                AND time_transaction_id IS NULL
                AND usage_session_id IS NOT NULL
            )
            """,
            name="ck_time_sales_result_by_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    sale_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    time_product_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "time_products.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    price_clp: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    actor_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    station_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "stations.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    time_transaction_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "time_transactions.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        unique=True,
    )

    usage_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "usage_sessions.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )