"""add custom scenario confidence threshold

Revision ID: 0008_add_custom_scenario_confidence_threshold
Revises: 0007_create_custom_scenarios
Create Date: 2026-06-12
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_add_custom_scenario_confidence_threshold"
down_revision = "0007_create_custom_scenarios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "custom_scenarios",
        sa.Column("confidence_threshold", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("custom_scenarios", "confidence_threshold")
