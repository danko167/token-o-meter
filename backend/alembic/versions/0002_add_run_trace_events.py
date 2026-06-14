"""add run trace events

Revision ID: 0002_add_run_trace_events
Revises: 0001_create_runs_table
Create Date: 2026-06-11 00:00:01.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_run_trace_events"
down_revision: str | None = "0001_create_runs_table"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("trace_events", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "trace_events")
