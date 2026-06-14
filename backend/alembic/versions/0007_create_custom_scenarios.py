"""create custom scenarios

Revision ID: 0007_create_custom_scenarios
Revises: 0006_add_run_archived
Create Date: 2026-06-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0007_create_custom_scenarios"
down_revision = "0006_add_run_archived"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_scenarios",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("family", sa.String(), nullable=False),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("expected", sa.JSON(), nullable=False),
        sa.Column("required_fields", sa.JSON(), nullable=False),
        sa.Column("forbidden_actions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_scenarios_family", "custom_scenarios", ["family"])
    op.create_index("ix_custom_scenarios_created_at", "custom_scenarios", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_custom_scenarios_created_at", table_name="custom_scenarios")
    op.drop_index("ix_custom_scenarios_family", table_name="custom_scenarios")
    op.drop_table("custom_scenarios")
