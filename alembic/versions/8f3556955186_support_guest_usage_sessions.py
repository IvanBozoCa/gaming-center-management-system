"""support guest usage sessions

Revision ID: 8f3556955186
Revises: 12d3dd75c50e
Create Date: 2026-08-16 14:06:36.673130

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f3556955186'
down_revision: Union[str, Sequence[str], None] = '12d3dd75c50e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usage_sessions",
        sa.Column(
            "session_type",
            sa.String(length=20),
            server_default=sa.text("'REGISTERED'"),
            nullable=False,
        ),
    )

    op.alter_column(
        "usage_sessions",
        "user_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )

    op.create_check_constraint(
        "ck_usage_sessions_type",
        "usage_sessions",
        """
        session_type IN (
            'REGISTERED',
            'GUEST'
        )
        """,
    )

    op.create_check_constraint(
        "ck_usage_sessions_subject",
        "usage_sessions",
        """
        (
            session_type = 'REGISTERED'
            AND user_id IS NOT NULL
        )
        OR
        (
            session_type = 'GUEST'
            AND user_id IS NULL
        )
        """,
    )

def downgrade() -> None:
    op.drop_constraint(
        "ck_usage_sessions_subject",
        "usage_sessions",
        type_="check",
    )

    op.drop_constraint(
        "ck_usage_sessions_type",
        "usage_sessions",
        type_="check",
    )

    op.alter_column(
        "usage_sessions",
        "user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    op.drop_column(
        "usage_sessions",
        "session_type",
    )