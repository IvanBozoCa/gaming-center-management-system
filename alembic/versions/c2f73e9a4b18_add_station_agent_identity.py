"""add station agent identity

Revision ID: c2f73e9a4b18
Revises: b488bfe49623
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


revision: str = "c2f73e9a4b18"

down_revision: (
    Union[
        str,
        Sequence[str],
        None,
    ]
) = "b488bfe49623"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stations",
        sa.Column(
            "agent_key_id",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "stations",
        sa.Column(
            "agent_secret_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "stations",
        sa.Column(
            "last_seen_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
        ),
    )

    op.create_unique_constraint(
        "uq_stations_agent_key_id",
        "stations",
        ["agent_key_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_stations_agent_key_id",
        "stations",
        type_="unique",
    )

    op.drop_column(
        "stations",
        "last_seen_at",
    )

    op.drop_column(
        "stations",
        "agent_secret_hash",
    )

    op.drop_column(
        "stations",
        "agent_key_id",
    )