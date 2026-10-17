"""The filters 8bf-host found, as the menus and settings dialog use them."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Filter:
    id: str
    name: str
    category: str
    path: str = ""
    archs: List[str] = field(default_factory=list)
    modes: List[str] = field(default_factory=list)
    has_about_box: bool = False
    # Where 8bf-host would run it, or None with ``problem`` saying why it cannot.
    runs: Optional[str] = None
    problem: Optional[str] = None

    @classmethod
    def from_json(cls, payload):
        return cls(
            id=str(payload["id"]),
            name=str(payload.get("name", "")),
            category=str(payload.get("category", "")) or "Other",
            path=str(payload.get("path", "")),
            archs=list(payload.get("archs") or []),
            modes=list(payload.get("modes") or []),
            has_about_box=bool(payload.get("has_about_box")),
            runs=payload.get("runs"),
            problem=payload.get("problem"),
        )

    @property
    def runnable(self):
        return self.runs is not None


class Catalog:
    def __init__(self):
        self.filters = []
        self.problems = []
        # Why the list could not be read at all (8bf-host missing or failing).
        self.error = None

    def load(self, filters, problems=()):
        entries = [Filter.from_json(payload) for payload in filters if payload.get("id")]
        entries.sort(key=lambda e: (e.category.lower(), e.name.lower()))
        self.filters = entries
        self.problems = [(str(p.get("path", "")), str(p.get("message", ""))) for p in problems]
        self.error = None

    def fail(self, message):
        self.filters = []
        self.problems = []
        self.error = message

    def find(self, filter_id):
        for entry in self.filters:
            if entry.id == filter_id:
                return entry
        return None

    def by_category(self):
        groups = {}
        for entry in self.filters:
            groups.setdefault(entry.category, []).append(entry)
        return groups
