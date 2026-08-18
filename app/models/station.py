from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


class Station(Base):
    __tablename__ = "stations"

    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'AVAILABLE',
                'IN_USE',
                'MAINTENANCE',
                'OFFLINE'
            )
            """,
            name="ck_stations_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="AVAILABLE",
        server_default=text("'AVAILABLE'"),
    )

    agent_key_id: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
    )

    agent_secret_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )