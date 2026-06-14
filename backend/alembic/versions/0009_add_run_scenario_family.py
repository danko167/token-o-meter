"""add scenario_family snapshot to runs

Revision ID: 0009_add_run_scenario_family
Revises: 0008_add_custom_scenario_confidence_threshold
Create Date: 2026-06-12
"""

from pathlib import Path

import sqlalchemy as sa
import yaml

from alembic import op

revision = "0009_add_run_scenario_family"
down_revision = "0008_add_custom_scenario_confidence_threshold"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("scenario_family", sa.String(), nullable=True))
    op.create_index("ix_runs_scenario_family", "runs", ["scenario_family"])
    _backfill_scenario_family()


def downgrade() -> None:
    op.drop_index("ix_runs_scenario_family", table_name="runs")
    op.drop_column("runs", "scenario_family")


def _backfill_scenario_family() -> None:
    """Snapshot each existing run's scenario family so it keeps appearing in
    family-filtered dashboards even if the scenario is later deleted."""
    bind = op.get_bind()
    family_by_scenario_id: dict[str, str] = {}

    scenarios_dir = Path(__file__).resolve().parents[2] / "scenarios"
    for path in scenarios_dir.glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "id" in data and "family" in data:
            family_by_scenario_id[data["id"]] = data["family"]

    custom_scenarios = sa.table(
        "custom_scenarios",
        sa.column("id", sa.String()),
        sa.column("family", sa.String()),
    )
    for row in bind.execute(sa.select(custom_scenarios.c.id, custom_scenarios.c.family)):
        family_by_scenario_id[row.id] = row.family

    runs = sa.table(
        "runs",
        sa.column("scenario_id", sa.String()),
        sa.column("scenario_family", sa.String()),
    )
    for scenario_id, family in family_by_scenario_id.items():
        bind.execute(
            runs.update().where(runs.c.scenario_id == scenario_id).values(scenario_family=family)
        )
