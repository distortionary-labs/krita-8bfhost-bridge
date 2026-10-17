"""Krita layer pixels to and from the image files 8bf-host reads and writes.

Krita hands out RGBA pixels as B,G,R,A, with 16-bit samples in the
machine's byte order. PAM files store R,G,B,A with 16-bit samples
big-endian. Both conversions are whole-buffer slice and array operations,
so the per-pixel work happens in C.
"""

import array
import sys

# (Krita color model, depth) -> (channels, bytes per sample)
FORMATS = {
    ("RGBA", "U8"): (4, 1),
    ("RGBA", "U16"): (4, 2),
    ("GRAYA", "U8"): (2, 1),
}

TUPLE_TYPES = {4: "RGB_ALPHA", 2: "GRAYSCALE_ALPHA"}


class UnsupportedLayer(ValueError):
    """The layer's color model or depth cannot be filtered."""


def layer_format(color_model, depth):
    """Return ``(channels, bytes per sample)`` for a Krita layer format."""
    found = FORMATS.get((color_model, depth))
    if found is not None:
        return found
    if (color_model, depth) == ("GRAYA", "U16"):
        raise UnsupportedLayer(
            "16-bit grayscale layers are not supported yet. Convert the layer to "
            "8-bit grayscale or to 16-bit RGB first."
        )
    raise UnsupportedLayer(
        "Only 8- and 16-bit RGB and 8-bit grayscale layers are supported; this layer is "
        "%s %s. Convert it first (Image > Convert Image Color Space)." % (color_model, depth)
    )


def _swap_red_blue(data, sample_bytes):
    out = bytearray(data)
    step = 4 * sample_bytes
    blue = 2 * sample_bytes
    for byte in range(sample_bytes):
        out[byte::step] = data[blue + byte :: step]
        out[blue + byte :: step] = data[byte::step]
    return out


def _swap_byte_order(data):
    if sys.byteorder == "big":
        return bytes(data)
    samples = array.array("H")
    samples.frombytes(bytes(data))
    samples.byteswap()
    return samples.tobytes()


def krita_to_pam(raw, channels, sample_bytes):
    """Convert ``Node.pixelData`` bytes to PAM sample order."""
    data = bytes(raw)
    if channels == 4:
        data = bytes(_swap_red_blue(data, sample_bytes))
    if sample_bytes == 2:
        data = _swap_byte_order(data)
    return data


# Both steps undo themselves, so the way back is the same conversion.
pam_to_krita = krita_to_pam


def write_pam(path, width, height, channels, sample_bytes, data):
    header = "P7\nWIDTH %d\nHEIGHT %d\nDEPTH %d\nMAXVAL %d\nTUPLTYPE %s\nENDHDR\n" % (
        width,
        height,
        channels,
        255 if sample_bytes == 1 else 65535,
        TUPLE_TYPES[channels],
    )
    with open(path, "wb") as handle:
        handle.write(header.encode("ascii"))
        handle.write(data)


def read_pam(path):
    """Return ``(width, height, channels, bytes per sample, data)``."""
    with open(path, "rb") as handle:
        content = handle.read()
    if not content.startswith(b"P7\n"):
        raise ValueError("%s is not a PAM file" % path)
    end = content.find(b"ENDHDR\n")
    if end < 0:
        raise ValueError("%s has no PAM header end" % path)
    fields = {}
    for line in content[3:end].split(b"\n"):
        parts = line.split(None, 1)
        if len(parts) == 2 and not parts[0].startswith(b"#"):
            fields[parts[0].decode("ascii")] = parts[1].strip()
    try:
        width = int(fields["WIDTH"])
        height = int(fields["HEIGHT"])
        channels = int(fields["DEPTH"])
        maxval = int(fields["MAXVAL"])
    except (KeyError, ValueError) as exc:
        raise ValueError("%s has an incomplete PAM header" % path) from exc
    sample_bytes = 1 if maxval < 256 else 2
    data = content[end + len(b"ENDHDR\n") :]
    expected = width * height * channels * sample_bytes
    if len(data) != expected:
        raise ValueError("%s holds %d bytes of pixels, expected %d" % (path, len(data), expected))
    return width, height, channels, sample_bytes, data


def write_pgm(path, width, height, data):
    """Write an 8-bit grayscale image, used for selection masks."""
    with open(path, "wb") as handle:
        handle.write(b"P5\n%d %d\n255\n" % (width, height))
        handle.write(data)
