"""The plug-in's commands and image files against a real 8bf-host.

Opt-in: set EIGHTBF_HOST to a dynamically linked build (``cargo build``).
"""

import json
import struct

from krita_8bfhost_bridge import host, images
from krita_8bfhost_bridge.catalog import Catalog


def _catalog(eightbf_host, folder):
    catalog = Catalog()
    catalog.load(*host.list_filters(eightbf_host, [folder], rescan=True))
    return catalog


def _run(eightbf_host, folder, filter_id, tmp_path, **options):
    command = host.run_command(
        eightbf_host,
        [folder],
        filter_id,
        str(tmp_path / "in.pam"),
        str(tmp_path / "out.pam"),
        dialog=False,
        **options,
    )
    return host.run(command)


def test_filters_are_listed(eightbf_host, filter_folder):
    catalog = _catalog(eightbf_host, filter_folder)
    assert sorted(entry.name for entry in catalog.filters) == ["Error", "Invert"]
    assert all(entry.runnable for entry in catalog.filters)


def test_8bit_layer_round_trip_with_preset(eightbf_host, filter_folder, tmp_path):
    invert = next(e for e in _catalog(eightbf_host, filter_folder).filters if e.name == "Invert")
    bgra = bytes(range(24))
    pam = images.krita_to_pam(bgra, 4, 1)
    images.write_pam(str(tmp_path / "in.pam"), 3, 2, 4, 1, pam)
    preset = str(tmp_path / "preset.json")

    result = _run(eightbf_host, filter_folder, invert.id, tmp_path, save_preset=preset)
    assert result.ok, result.message
    width, height, channels, sample_bytes, data = images.read_pam(str(tmp_path / "out.pam"))
    assert (width, height, channels, sample_bytes) == (3, 2, 4, 1)
    out = images.pam_to_krita(data, 4, 1)
    assert list(out[:4]) == [255, 254, 253, 3]
    assert json.load(open(preset))["format"] == "8bf-host-preset"

    # Repeat: replay the preset without the dialog.
    result = _run(eightbf_host, filter_folder, invert.id, tmp_path, preset=preset)
    assert result.ok, result.message


def test_16bit_layer_with_selection(eightbf_host, filter_folder, tmp_path):
    invert = next(e for e in _catalog(eightbf_host, filter_folder).filters if e.name == "Invert")
    samples = [i * 1000 + 1 for i in range(8)]
    bgra = struct.pack("<8H", *samples)
    images.write_pam(str(tmp_path / "in.pam"), 2, 1, 4, 2, images.krita_to_pam(bgra, 4, 2))
    images.write_pgm(str(tmp_path / "mask.pgm"), 2, 1, b"\xff\x00")

    result = _run(
        eightbf_host,
        filter_folder,
        invert.id,
        tmp_path,
        mask=str(tmp_path / "mask.pgm"),
        rect=(0, 0, 1, 1),
    )
    assert result.ok, result.message
    _w, _h, _c, sample_bytes, data = images.read_pam(str(tmp_path / "out.pam"))
    assert sample_bytes == 2
    out = struct.unpack("<8H", images.pam_to_krita(data, 4, 2))
    # The selected pixel is inverted (through the 8-bit fallback), alpha kept.
    assert all(abs(out[i] - (65535 - samples[i])) <= 300 for i in range(3))
    assert out[3] == samples[3]
    # The unselected pixel is bit-for-bit unchanged.
    assert list(out[4:]) == samples[4:]


def test_filter_errors_come_back_as_messages(eightbf_host, filter_folder, tmp_path):
    error = next(e for e in _catalog(eightbf_host, filter_folder).filters if e.name == "Error")
    images.write_pam(str(tmp_path / "in.pam"), 1, 1, 4, 1, bytes(4))
    result = _run(eightbf_host, filter_folder, error.id, tmp_path)
    assert result.status == "error"
    assert "failed on purpose" in result.message
