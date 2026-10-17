import os

from krita_8bfhost_bridge import settings as settings_module
from krita_8bfhost_bridge.catalog import Catalog, Filter


def test_settings_round_trip():
    backend = settings_module.DictBackend()
    original = settings_module.Settings(
        host_path="/opt/8bf-host",
        folders=["/a", "/b c"],
        apply_mode=settings_module.APPLY_IN_PLACE,
        allow_8bit_fallback=False,
    )
    settings_module.save(original, backend)
    assert backend.data["folders"] == '["/a", "/b c"]'
    assert settings_module.load(backend) == original


def test_settings_ignore_garbage():
    backend = settings_module.DictBackend({"folders": "not json", "allow_8bit_fallback": "no"})
    loaded = settings_module.load(backend)
    assert loaded.allow_8bit_fallback is False
    assert loaded.folders == []


def test_preset_store(tmp_path):
    store = settings_module.PresetStore(str(tmp_path / "presets"))
    assert store.existing("1a2b3c4d5e6f") is None
    path = store.path("1a2b3c4d5e6f")
    assert os.path.dirname(path) == str(tmp_path / "presets")
    open(path, "w").write("{}")
    assert store.existing("1a2b3c4d5e6f") == path
    # Ids come from 8bf-host, but never let one name a path outside the folder.
    assert os.path.dirname(store.path("../x")) == str(tmp_path / "presets")


def summary(**values):
    payload = {
        "id": "8c8224326f39",
        "name": "Invert",
        "category": "Wine",
        "path": "/f/invert.8bf",
        "format": "pe",
        "archs": ["win-x64"],
        "modes": ["rgb8", "gray8"],
        "has_about_box": True,
        "runs": "under Wine (win-x64)",
        "problem": None,
    }
    payload.update(values)
    return payload


def test_filter_from_list_json():
    entry = Filter.from_json(summary())
    assert entry.id == "8c8224326f39"
    assert entry.runnable
    assert entry.has_about_box
    blocked = Filter.from_json(summary(runs=None, problem="needs Wine"))
    assert not blocked.runnable
    assert blocked.problem == "needs Wine"
    assert Filter.from_json(summary(category="")).category == "Other"


def test_catalog():
    catalog = Catalog()
    catalog.load(
        [
            summary(id="b", name="zeta", category="Two"),
            summary(id="a", name="Alpha", category="one"),
            summary(id="c", name="beta", category="Two"),
            {"name": "no id"},
        ],
        [{"path": "/f/broken.8bf", "message": "no PiPL"}],
    )
    assert [entry.id for entry in catalog.filters] == ["a", "c", "b"]
    assert catalog.find("c").name == "beta"
    assert catalog.find("missing") is None
    assert list(catalog.by_category()) == ["one", "Two"]
    assert catalog.problems == [("/f/broken.8bf", "no PiPL")]
    assert catalog.error is None

    catalog.fail("8bf-host was not found")
    assert catalog.filters == []
    assert catalog.error == "8bf-host was not found"
