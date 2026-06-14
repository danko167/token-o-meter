"""Loads scenario definitions from YAML files at startup."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.db.migrations import run_migrations
from app.db.models import ScenarioRecord, record_from_scenario, scenario_from_record
from app.schemas.scenario import Scenario, ScenarioCreate, ScenarioSummary

logger = logging.getLogger(__name__)


class ScenarioNotFoundError(KeyError):
    pass


class ScenarioAlreadyExistsError(ValueError):
    pass


class BuiltInScenarioError(ValueError):
    pass


class ScenarioStore:
    def __init__(self, scenarios_dir: Path, database_path: Path, migrate: bool = True) -> None:
        self._dir = scenarios_dir
        self._scenarios: dict[str, Scenario] = {}
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        if migrate:
            run_migrations(self._database_path)
        self._engine = create_engine(
            f"sqlite:///{self._database_path}",
            connect_args={"check_same_thread": False},
        )
        self._session_factory = sessionmaker(bind=self._engine)

    def load(self) -> None:
        self._scenarios.clear()
        if not self._dir.is_dir():
            logger.warning("scenarios directory %s does not exist", self._dir)
            return
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                scenario = Scenario.model_validate(data)
            except Exception:
                logger.exception("failed to load scenario file %s", path.name)
                continue
            self._scenarios[scenario.id] = scenario.model_copy(update={"is_custom": False})
        logger.info("loaded %d scenario(s) from %s", len(self._scenarios), self._dir)

    def list(self) -> list[ScenarioSummary]:
        scenarios = [*self._scenarios.values(), *self._list_custom()]
        return [
            ScenarioSummary(
                id=s.id,
                name=s.name,
                description=s.description,
                family=s.family,
                is_custom=s.is_custom,
            )
            for s in scenarios
        ]

    def get(self, scenario_id: str) -> Scenario:
        if scenario_id in self._scenarios:
            return self._scenarios[scenario_id]

        with self._session_factory() as session:
            record = session.get(ScenarioRecord, scenario_id)
            if record is not None:
                return scenario_from_record(record)
        raise ScenarioNotFoundError(scenario_id) from None

    def create(self, payload: ScenarioCreate) -> Scenario:
        scenario_id = _scenario_id(payload.id or payload.name)
        if scenario_id in self._scenarios:
            raise ScenarioAlreadyExistsError(scenario_id)

        with self._session_factory() as session:
            if session.get(ScenarioRecord, scenario_id) is not None:
                raise ScenarioAlreadyExistsError(scenario_id)

            scenario = Scenario(
                id=scenario_id,
                name=payload.name,
                description=payload.description,
                family=payload.family,
                input=payload.input,
                expected=payload.expected,
                required_fields=payload.required_fields,
                forbidden_actions=payload.forbidden_actions,
                confidence_threshold=payload.confidence_threshold,
                is_custom=True,
            )
            session.merge(record_from_scenario(scenario))
            session.commit()
            return scenario

    def delete_custom(self, scenario_id: str) -> None:
        if scenario_id in self._scenarios:
            raise BuiltInScenarioError(scenario_id)
        with self._session_factory() as session:
            result = session.execute(delete(ScenarioRecord).where(ScenarioRecord.id == scenario_id))
            session.commit()
            if not result.rowcount:
                raise ScenarioNotFoundError(scenario_id)

    def _list_custom(self) -> list[Scenario]:
        with self._session_factory() as session:
            records = session.scalars(
                select(ScenarioRecord).order_by(ScenarioRecord.created_at.desc())
            ).all()
            return [scenario_from_record(record) for record in records]


def _scenario_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "custom-scenario"
