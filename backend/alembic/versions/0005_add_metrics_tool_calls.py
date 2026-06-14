"""add metrics tool calls

Revision ID: 0005_add_metrics_tool_calls
Revises: 0004_add_run_is_demo
Create Date: 2026-06-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0005_add_metrics_tool_calls"
down_revision = "0004_add_run_is_demo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("metrics_tool_calls", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "metrics_tool_calls")
