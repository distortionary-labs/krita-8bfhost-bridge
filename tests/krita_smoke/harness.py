"""A throwaway Krita plug-in that drives krita_8bfhost_bridge inside a real Krita.

run.sh installs this as the ``k8bfsmoke`` plug-in in a temporary profile.
It creates documents, runs the test filter through the extension (menu
code, bridge and 8bf-host), checks the pixels and writes a JSON report
to $K8BF_SMOKE_REPORT before exiting Krita.
"""

import json
import os
import traceback

from krita import Extension, Krita, Selection
from PyQt5.QtCore import QByteArray, QTimer

REPORT = os.environ["K8BF_SMOKE_REPORT"]
FOLDER = os.environ["K8BF_SMOKE_PLUGINS"]
HOST = os.environ["EIGHTBF_HOST"]
WIDTH, HEIGHT = 8, 6


class _Messages:
    """Stands in for QMessageBox so a failure cannot block the run."""

    shown = []

    @classmethod
    def warning(cls, _parent, _title, text):
        cls.shown.append(text)

    information = warning


class _Document:
    """Under Xvfb no view gets focus, so Document.activeNode() stays None.

    Pin the active node so the extension sees the layer the smoke test made.
    """

    def __init__(self, document, node):
        self._document = document
        self._node = node

    def activeNode(self):
        return self._node

    def setActiveNode(self, node):
        self._node = node
        self._document.setActiveNode(node)

    def __getattr__(self, name):
        return getattr(self._document, name)


class _Krita:
    def __init__(self, krita, document):
        self._krita = krita
        self._document = document

    def activeDocument(self):
        return self._document

    def __getattr__(self, name):
        return getattr(self._krita, name)


def _samples(raw, bps):
    if bps == 1:
        return list(raw)
    return [int.from_bytes(raw[i : i + 2], "little") for i in range(0, len(raw), 2)]


class Smoke(Extension):
    def setup(self):
        pass

    def createActions(self, window):
        QTimer.singleShot(1500, self.run)

    def check(self, name, condition, detail=""):
        self.report["checks"].append({"name": name, "ok": bool(condition), "detail": detail})

    def run(self):
        self.report = {"checks": []}
        try:
            self._run()
        except Exception:
            self.report["error"] = traceback.format_exc()
        self.report["messages"] = _Messages.shown
        self.report["ok"] = "error" not in self.report and all(
            c["ok"] for c in self.report["checks"]
        )
        with open(REPORT, "w") as handle:
            json.dump(self.report, handle, indent=1)
        os._exit(0)

    def _run(self):
        import krita_8bfhost_bridge.extension as extension_module

        extension_module.QMessageBox = _Messages
        krita = Krita.instance()
        extension = next(
            e for e in krita.extensions() if type(e).__name__ == "Krita8bfhostBridgeExtension"
        )
        extension.settings.host_path = HOST
        extension.settings.folders = [FOLDER]
        extension._scan(rescan=True)
        names = [entry.name for entry in extension.catalog.filters]
        self.check("filter discovered", names == ["Smoke Invert"], names)
        menu = [action.text() for menu in extension.menus for action in menu.actions()]
        self.check("menu rebuilt", "Smoke Tests" in menu, menu)
        filter_id = extension.catalog.filters[0].id

        for depth, bps in (("U8", 1), ("U16", 2)):
            document = krita.createDocument(WIDTH, HEIGHT, "smoke" + depth, "RGBA", depth, "", 72.0)
            krita.activeWindow().addView(document)
            node = document.createNode("Paint", "paintlayer")
            document.rootNode().addChildNode(node, None)
            count = WIDTH * HEIGHT * 4
            if bps == 1:
                data = bytes((i * 5) % 256 for i in range(count))
            else:
                data = b"".join(((i * 1000) % 65536).to_bytes(2, "little") for i in range(count))
            node.setPixelData(QByteArray(data), 0, 0, WIDTH, HEIGHT)
            document.waitForDone()
            proxy = _Document(document, node)
            extension.krita = _Krita(krita, proxy)

            extension.settings.apply_mode = "new-layer"
            extension.run_filter(filter_id)
            document.waitForDone()
            layers = [child.name() for child in document.rootNode().childNodes()]
            self.check(depth + " new layer", "Paint (Smoke Invert)" in layers, layers)
            output = _samples(bytes(proxy.activeNode().pixelData(0, 0, WIDTH, HEIGHT)), bps)
            source = _samples(data, bps)
            top = 255 if bps == 1 else 65535
            tolerance = 0 if bps == 1 else 300  # 16-bit runs through the 8-bit fallback
            colour_ok = all(
                abs(output[i] - (top - source[i])) <= tolerance
                for i in range(len(source))
                if i % 4 != 3
            )
            alpha_ok = all(output[i] == source[i] for i in range(3, len(source), 4))
            self.check(depth + " colours inverted", colour_ok, output[:8])
            self.check(depth + " alpha kept", alpha_ok)

            # Repeat in place with a 2x1 selection: only those pixels change.
            extension.settings.apply_mode = "in-place"
            selection = Selection()
            selection.select(0, 0, 2, 1, 255)
            document.setSelection(selection)
            proxy.setActiveNode(node)
            extension.repeat_last()
            document.waitForDone()
            after = _samples(bytes(node.pixelData(0, 0, WIDTH, HEIGHT)), bps)
            inside = all(
                abs(after[i] - (top - source[i])) <= tolerance for i in range(8) if i % 4 != 3
            )
            outside = after[8:] == source[8:]
            self.check(depth + " selection inverted", inside, after[:8])
            self.check(depth + " outside selection untouched", outside)
            document.setModified(False)


Krita.instance().addExtension(Smoke(Krita.instance()))
