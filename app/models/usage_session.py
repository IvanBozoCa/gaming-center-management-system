from datetime import datetime
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
    text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.core.database import Base


class UsageSession(Base):
    __tablename__ = "usage_sessions"

    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'ACTIVE',
                'FINISHED'
            )
            """,
            name="ck_usage_sessions_status",
        ),
        CheckConstraint(
            "authorized_seconds > 0",
            name="ck_usage_sessions_authorized_positive",
        ),
        Index(
            "uq_usage_sessions_active_station",
            "station_id",
            unique=True,
            postgresql_where=text(
                "status = 'ACTIVE'"
            ),
        ),
        Index(
            "uq_usage_sessions_active_user",
            "user_id",
            unique=True,
            postgresql_where=text(
                "status = 'ACTIVE'"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "stations.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default=text("'ACTIVE'"),
    )

    authorized_seconds: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )