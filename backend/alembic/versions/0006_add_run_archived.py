"""add run archived flag

Revision ID: 0006_add_run_archived
Revises: 0005_add_metrics_tool_calls
Create Date: 2026-06-11 00:00:05.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_add_run_archived"
down_revision: str | None = "0005_add_metrics_tool_calls"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("archived", sa.Boolean(), nullable=False, server_default="0"))
    op.create_index("ix_runs_archived", "runs", ["archived"])


def downgrade() -> None:
    op.drop_index("ix_runs_archived", table_name="runs")
    op.drop_column("runs", "archived")
