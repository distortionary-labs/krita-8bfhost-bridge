"""User settings and stored filter presets.

``Settings`` is a plain dataclass; ``load`` and ``save`` take a backend
with ``read(key, default)`` and ``write(key, value)`` so the same code is
used with Krita's settings store and with a dict in the tests.
"""

import json
import os
import re
from dataclasses import asdict, dataclass, field, fields
from typing import List

GROUP = "krita_8bfhost_bridge"

APPLY_NEW_LAYER = "new-layer"
APPLY_IN_PLACE = "in-place"


@dataclass
class Settings:
    # The 8bf-host program. Empty means "look for it".
    host_path: str = ""
    # Extra filter folders. 8bf-host adds the usual Adobe folders and its own
    # configured ones by itself.
    folders: List[str] = field(default_factory=list)
    apply_mode: str = APPLY_NEW_LAYER
    allow_8bit_fallback: bool = True

    def to_dict(self):
        return asdict(self)


def load(backend):
    """Read settings from a backend, falling back to defaults."""
    settings = Settings()
    for item in fields(Settings):
        raw = backend.read(item.name, None)
        if raw is None or raw == "":
            continue
        current = getattr(settings, item.name)
        try:
            if isinstance(current, bool):
                value = raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true", "yes")
            elif isinstance(current, list):
                value = raw if isinstance(raw, list) else json.loads(raw)
                value = [str(entry) for entry in value]
            else:
                value = str(raw)
        except (ValueError, TypeError):
            continue
        setattr(settings, item.name, value)
    return settings


def save(settings, backend):
    for item in fields(Settings):
        value = getattr(settings, item.name)
        if isinstance(value, list):
            value = json.dumps(value)
        elif isinstance(value, bool):
            value = "true" if value else "false"
        backend.write(item.name, value)


class DictBackend:
    """Settings backend over a dict, for tests and headless use."""

    def __init__(self, data=None):
        self.data = dict(data or {})

    def read(self, key, default):
        return self.data.get(key, default)

    def write(self, key, value):
        self.data[key] = value


class KritaBackend:
    """Settings backend over Krita's kritarc."""

    def __init__(self, krita):
        self.krita = krita

    def read(self, key, default):
        value = self.krita.readSetting(GROUP, key, "")
        return value if value != "" else default

    def write(self, key, value):
        self.krita.writeSetting(GROUP, key, str(value))


class PresetStore:
    """Where each filter's last settings live, as 8bf-host preset files.

    8bf-host writes the preset after a run (``--save-preset``) and reads it
    for the next one (``--preset``), which is what Repeat uses.
    """

    def __init__(self, directory):
        self.directory = directory

    def path(self, filter_id):
        os.makedirs(self.directory, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", filter_id)
        return os.path.join(self.directory, safe + ".json")

    def existing(self, filter_id):
        """Return the preset path when one was saved, else None."""
        path = self.path(filter_id)
        return path if os.path.isfile(path) and os.path.getsize(path) > 0 else None
