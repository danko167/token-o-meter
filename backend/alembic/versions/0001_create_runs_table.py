"""create runs table

Revision ID: 0001_create_runs_table
Revises:
Create Date: 2026-06-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_create_runs_table"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("scenario_id", sa.String(), nullable=False),
        sa.Column("runner", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metrics_duration_ms", sa.Float(), nullable=False),
        sa.Column("metrics_prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("metrics_completion_tokens", sa.Integer(), nullable=False),
        sa.Column("metrics_estimated_cost_usd", sa.Float(), nullable=False),
        sa.Column("metrics_retries", sa.Integer(), nullable=False),
        sa.Column("evaluation_score", sa.Integer(), nullable=True),
        sa.Column("evaluation_checks", sa.JSON(), nullable=True),
        sa.Column("pending_approval_action", sa.String(), nullable=True),
        sa.Column("pending_approval_reason", sa.Text(), nullable=True),
        sa.Column("pending_approval_details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runs_scenario_id", "runs", ["scenario_id"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_created_at", "runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_runs_created_at", table_name="runs")
    op.drop_index("ix_runs_status", table_name="runs")
    op.drop_index("ix_runs_scenario_id", table_name="runs")
    op.drop_table("runs")
