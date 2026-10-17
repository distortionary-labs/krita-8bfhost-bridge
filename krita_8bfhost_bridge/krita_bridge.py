"""Moving pixels between Krita layers and the files 8bf-host works on."""

import os
from dataclasses import dataclass

from . import images
from .qt import QByteArray

PAINT_LAYER = "paintlayer"
INPUT_NAME = "layer.pam"
OUTPUT_NAME = "filtered.pam"
MASK_NAME = "selection.pgm"


class BridgeError(RuntimeError):
    """The active document or layer cannot be filtered."""


@dataclass
class LayerJob:
    document: object
    node: object
    width: int
    height: int
    color_model: str
    depth: str
    channels: int
    sample_bytes: int
    input_path: str
    output_path: str
    mask_path: str = None
    # (x, y, width, height) of the selection's bounds, or None.
    rect: tuple = None
    foreground: tuple = (0, 0, 0)
    background: tuple = (255, 255, 255)
    resolution: float = 72.0


def _view_colors(krita):
    window = krita.activeWindow()
    view = window.activeView() if window else None
    if view is None:
        return (0, 0, 0), (255, 255, 255)
    canvas = view.canvas()

    def rgb(managed):
        try:
            color = managed.colorForCanvas(canvas)
            return (color.red(), color.green(), color.blue())
        except (AttributeError, RuntimeError):
            return None

    foreground = rgb(view.foregroundColor()) or (0, 0, 0)
    background = rgb(view.backgroundColor()) or (255, 255, 255)
    return foreground, background


def capture(krita, directory):
    """Write the active layer, and the selection if any, into ``directory``."""
    document = krita.activeDocument()
    if document is None:
        raise BridgeError("Open an image first.")
    node = document.activeNode()
    if node is None or node.type() != PAINT_LAYER:
        raise BridgeError("Select a paint layer to filter.")
    if node.locked():
        raise BridgeError("The active layer is locked.")
    color_model = node.colorModel()
    depth = node.colorDepth()
    try:
        channels, sample_bytes = images.layer_format(color_model, depth)
    except images.UnsupportedLayer as exc:
        raise BridgeError(str(exc)) from exc

    width, height = document.width(), document.height()
    document.waitForDone()
    raw = bytes(node.pixelData(0, 0, width, height))
    input_path = os.path.join(directory, INPUT_NAME)
    images.write_pam(
        input_path,
        width,
        height,
        channels,
        sample_bytes,
        images.krita_to_pam(raw, channels, sample_bytes),
    )

    mask_path = None
    rect = None
    selection = document.selection()
    if selection is not None and selection.width() > 0 and selection.height() > 0:
        mask_path = os.path.join(directory, MASK_NAME)
        images.write_pgm(mask_path, width, height, bytes(selection.pixelData(0, 0, width, height)))
        rect = (selection.x(), selection.y(), selection.width(), selection.height())

    foreground, background = _view_colors(krita)
    return LayerJob(
        document=document,
        node=node,
        width=width,
        height=height,
        color_model=color_model,
        depth=depth,
        channels=channels,
        sample_bytes=sample_bytes,
        input_path=input_path,
        output_path=os.path.join(directory, OUTPUT_NAME),
        mask_path=mask_path,
        rect=rect,
        foreground=foreground,
        background=background,
        resolution=float(document.resolution() or 72),
    )


def apply(job, new_layer_name=None):
    """Write 8bf-host's output back, in place or into a new layer above."""
    try:
        width, height, channels, sample_bytes, data = images.read_pam(job.output_path)
    except (OSError, ValueError) as exc:
        raise BridgeError("Could not read the filtered image: %s" % exc) from exc
    if (width, height, channels, sample_bytes) != (
        job.width,
        job.height,
        job.channels,
        job.sample_bytes,
    ):
        raise BridgeError("8bf-host returned an image of a different size or layout.")
    data = images.pam_to_krita(data, channels, sample_bytes)
    target = job.node
    if new_layer_name:
        target = job.document.createNode(new_layer_name, PAINT_LAYER)
        target.setColorSpace(job.color_model, job.depth, job.node.colorProfile())
        parent = job.node.parentNode()
        parent.addChildNode(target, job.node)
    target.setPixelData(QByteArray(data), 0, 0, job.width, job.height)
    job.document.refreshProjection()
    if new_layer_name:
        job.document.setActiveNode(target)
    return target
