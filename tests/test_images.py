import struct

import pytest

from krita_8bfhost_bridge import images


def test_supported_layer_formats():
    assert images.layer_format("RGBA", "U8") == (4, 1)
    assert images.layer_format("RGBA", "U16") == (4, 2)
    assert images.layer_format("GRAYA", "U8") == (2, 1)
    with pytest.raises(images.UnsupportedLayer, match="16-bit grayscale"):
        images.layer_format("GRAYA", "U16")
    with pytest.raises(images.UnsupportedLayer, match="CMYKA U8"):
        images.layer_format("CMYKA", "U8")


def test_8bit_rgba_swaps_blue_and_red():
    bgra = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    assert images.krita_to_pam(bgra, 4, 1) == bytes([3, 2, 1, 4, 7, 6, 5, 8])
    assert images.pam_to_krita(images.krita_to_pam(bgra, 4, 1), 4, 1) == bgra


def test_16bit_rgba_swaps_channels_and_byte_order():
    # One pixel: B=1, G=2, R=3, A=0xABCD, little-endian as Krita gives them.
    bgra = struct.pack("<4H", 1, 2, 3, 0xABCD)
    assert images.krita_to_pam(bgra, 4, 2) == struct.pack(">4H", 3, 2, 1, 0xABCD)
    assert images.pam_to_krita(images.krita_to_pam(bgra, 4, 2), 4, 2) == bgra


def test_grayscale_is_left_alone():
    assert images.krita_to_pam(bytes([9, 200]), 2, 1) == bytes([9, 200])


def test_pam_round_trip(tmp_path):
    path = str(tmp_path / "image.pam")
    data = bytes(range(24))
    images.write_pam(path, 3, 2, 4, 1, data)
    assert open(path, "rb").read().startswith(b"P7\nWIDTH 3\nHEIGHT 2\nDEPTH 4\nMAXVAL 255\n")
    assert images.read_pam(path) == (3, 2, 4, 1, data)

    images.write_pam(path, 1, 1, 4, 2, bytes(8))
    assert images.read_pam(path) == (1, 1, 4, 2, bytes(8))


def test_pam_comments_are_skipped(tmp_path):
    path = tmp_path / "image.pam"
    path.write_bytes(
        b"P7\n# a comment\nWIDTH 1\nHEIGHT 1\nDEPTH 2\nMAXVAL 255\n"
        b"TUPLTYPE GRAYSCALE_ALPHA\nENDHDR\n\x10\x20"
    )
    assert images.read_pam(str(path)) == (1, 1, 2, 1, b"\x10\x20")


@pytest.mark.parametrize(
    "content, message",
    [
        (b"P6\n1 1\n255\n\0\0\0", "not a PAM"),
        (b"P7\nWIDTH 1\n", "no PAM header end"),
        (b"P7\nWIDTH 1\nENDHDR\n", "incomplete"),
        (b"P7\nWIDTH 1\nHEIGHT 1\nDEPTH 4\nMAXVAL 255\nENDHDR\n\0", "expected 4"),
    ],
)
def test_broken_pam_files(tmp_path, content, message):
    path = tmp_path / "broken.pam"
    path.write_bytes(content)
    with pytest.raises(ValueError, match=message):
        images.read_pam(str(path))


def test_mask_is_a_pgm(tmp_path):
    path = tmp_path / "mask.pgm"
    images.write_pgm(str(path), 2, 1, b"\xff\x00")
    assert path.read_bytes() == b"P5\n2 1\n255\n\xff\x00"
