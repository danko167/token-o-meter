"""add run is_demo flag

Revision ID: 0004_add_run_is_demo
Revises: 0003_add_human_evaluation
Create Date: 2026-06-11 00:00:03.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_add_run_is_demo"
down_revision: str | None = "0003_add_human_evaluation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default="0"))
    op.create_index("ix_runs_is_demo", "runs", ["is_demo"])


def downgrade() -> None:
    op.drop_index("ix_runs_is_demo", table_name="runs")
    op.drop_column("runs", "is_demo")
