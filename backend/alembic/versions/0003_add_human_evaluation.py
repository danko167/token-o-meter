"""add human evaluation fields

Revision ID: 0003_add_human_evaluation
Revises: 0002_add_run_trace_events
Create Date: 2026-06-11 00:00:02.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_add_human_evaluation"
down_revision: str | None = "0002_add_run_trace_events"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("human_evaluation_score", sa.Integer(), nullable=True))
    op.add_column("runs", sa.Column("human_evaluation_useful", sa.Boolean(), nullable=True))
    op.add_column("runs", sa.Column("human_evaluation_correct", sa.Boolean(), nullable=True))
    op.add_column("runs", sa.Column("human_evaluation_comment", sa.Text(), nullable=True))
    op.add_column(
        "runs",
        sa.Column("human_evaluation_created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("runs", "human_evaluation_created_at")
    op.drop_column("runs", "human_evaluation_comment")
    op.drop_column("runs", "human_evaluation_correct")
    op.drop_column("runs", "human_evaluation_useful")
    op.drop_column("runs", "human_evaluation_score")
