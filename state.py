import json

from pathlib import Path
from datetime import datetime

from models import SourceState


class StateManager:

    def __init__(self, path: str):

        self.path = Path(path)

        self.sources = {}

    def load(self):

        if not self.path.exists():

            return

        with self.path.open(encoding="utf-8") as f:

            data = json.load(f)

        for name, value in data.get("sources", {}).items():

            self.sources[name] = SourceState(
                status=value.get("status", "available"),
                processed=set(value.get("processed", [])),
                last_success=self.parse_date(value.get("last_success")),
                unavailable_since=self.parse_date(value.get("unavailable_since")),
                next_check=self.parse_date(value.get("next_check")),
                failed_attempts=value.get("failed_attempts", 0),
                alert_sent=value.get("alert_sent", False),
            )

    def save(self):

        data = {"sources": {}}

        for name, state in self.sources.items():

            data["sources"][name] = {
                "status": state.status,
                "processed": list(state.processed),
                "last_success": self.format_date(state.last_success),
                "unavailable_since": self.format_date(state.unavailable_since),
                "next_check": self.format_date(state.next_check),
                "failed_attempts": state.failed_attempts,
                "alert_sent": state.alert_sent,
            }

        tmp = self.path.with_suffix(".tmp")

        with tmp.open("w", encoding="utf-8") as f:

            json.dump(data, f, indent=2)

        tmp.replace(self.path)

    def get(self, name: str) -> SourceState:

        if name not in self.sources:

            self.sources[name] = SourceState()

        return self.sources[name]

    @staticmethod
    def parse_date(value):

        if not value:
            return None

        return datetime.fromisoformat(value)

    @staticmethod
    def format_date(value):

        if not value:
            return None

        return value.isoformat()
