"""Tracks progress of the demo data execution for status polling.

A single instance lives on `app.state.demo_progress` so that
GET /demo-data/execute/status can report live progress while
POST /demo-data/execute is still running.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DemoExecutionProgress:
    running: bool = False
    done: bool = True
    current: int = 0
    total: int = 0
    message: str = "Idle"
    error: str | None = None

    def start(self, total: int, message: str) -> None:
        self.running = True
        self.done = False
        self.current = 0
        self.total = total
        self.message = message
        self.error = None

    def step(self, current: int, message: str) -> None:
        self.current = current
        self.message = message

    def finish(self, message: str) -> None:
        self.running = False
        self.done = True
        self.message = message

    def fail(self, message: str) -> None:
        self.running = False
        self.done = True
        self.error = message

    def snapshot(self) -> dict[str, object]:
        return {
            "running": self.running,
            "done": self.done,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "error": self.error,
        }
