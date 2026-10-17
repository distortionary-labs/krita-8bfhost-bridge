"""krita-8bfhost-bridge: run Photoshop-compatible filter plug-ins (.8bf) in Krita."""

__version__ = "0.1.0"

try:
    from krita import Krita
except ImportError:  # Imported outside Krita, e.g. by the tests or the host CLI.
    Krita = None

if Krita is not None:
    from .extension import Krita8bfhostBridgeExtension

    Krita.instance().addExtension(Krita8bfhostBridgeExtension(Krita.instance()))
