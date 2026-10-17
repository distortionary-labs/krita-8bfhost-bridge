"""The Krita extension: menus, actions and the glue between the parts."""

import os
import shutil
import sys
import tempfile

from krita import Extension, Krita

from . import host, krita_bridge
from . import settings as settings_module
from .catalog import Catalog
from .dialogs import FilterProgress, SettingsDialog
from .qt import QApplication, QMenu, QMessageBox, QStandardPaths, enum

MENU_TITLE = "Photoshop Filters (8bf)"
MENU_LOCATION = "tools/scripts"


def _data_dir():
    location = enum(QStandardPaths, "StandardLocation", "AppDataLocation")
    return os.path.join(QStandardPaths.writableLocation(location), "krita_8bfhost_bridge")


def _exec(dialog):
    return dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()


class Krita8bfhostBridgeExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.krita = Krita.instance()
        self.backend = settings_module.KritaBackend(self.krita)
        self.settings = settings_module.Settings()
        self.catalog = Catalog()
        self.presets = None
        self.menus = []
        self.repeat_actions = []
        self.last_id = None

    # Krita hooks -------------------------------------------------------------

    def setup(self):
        self.settings = settings_module.load(self.backend)
        self.presets = settings_module.PresetStore(os.path.join(_data_dir(), "presets"))
        self.last_id = self.krita.readSetting(settings_module.GROUP, "last_filter", "") or None
        self._scan()

    def createActions(self, window):
        menu_action = window.createAction("krita_8bfhost_bridge_filters", MENU_TITLE, MENU_LOCATION)
        menu = QMenu(MENU_TITLE, window.qwindow())
        menu_action.setMenu(menu)
        self.menus.append(menu)

        repeat = window.createAction(
            "krita_8bfhost_bridge_repeat", "Repeat Last 8bf Filter", MENU_LOCATION
        )
        repeat.triggered.connect(self.repeat_last)
        self.repeat_actions.append(repeat)

        configure = window.createAction(
            "krita_8bfhost_bridge_settings", "8bf Filter Settings…", MENU_LOCATION
        )
        configure.triggered.connect(self.show_settings)
        self._rebuild_menu(menu)
        self._update_repeat()

    # Catalog and menus -------------------------------------------------------

    def _scan(self, rescan=False, settings=None):
        settings = settings or self.settings
        try:
            executable = host.require_executable(settings.host_path)
            filters, problems = host.list_filters(executable, settings.folders, rescan)
            self.catalog.load(filters, problems)
        except host.HostError as exc:
            self.catalog.fail(str(exc))
            self._log("listing filters failed: %s" % exc)
        for menu in self.menus:
            self._rebuild_menu(menu)
        self._update_repeat()

    def _rebuild_menu(self, menu):
        menu.clear()
        groups = self.catalog.by_category()
        if not groups:
            label = (
                "8bf-host not set up — open 8bf Filter Settings"
                if self.catalog.error
                else "No filters found — open 8bf Filter Settings"
            )
            empty = menu.addAction(label)
            empty.triggered.connect(self.show_settings)
            return
        for category in sorted(groups, key=str.lower):
            submenu = menu.addMenu(category)
            for entry in groups[category]:
                action = submenu.addAction(entry.name + "…")
                action.triggered.connect(
                    lambda _checked=False, filter_id=entry.id: self.run_filter(filter_id)
                )
                if not entry.runnable:
                    action.setEnabled(False)
                    action.setToolTip(entry.problem or "Cannot run on this computer.")
        menu.addSeparator()
        rescan = menu.addAction("Rescan Filter Folders")
        rescan.triggered.connect(lambda _checked=False: self._scan(rescan=True))

    def _update_repeat(self):
        entry = self.catalog.find(self.last_id) if self.last_id else None
        for action in self.repeat_actions:
            action.setEnabled(entry is not None and entry.runnable)
            action.setText("Repeat %s" % entry.name if entry else "Repeat Last 8bf Filter")

    # Running filters ---------------------------------------------------------

    def _window(self):
        window = self.krita.activeWindow()
        return window.qwindow() if window else None

    def _log(self, message):
        if os.environ.get("KRITA_8BFHOST_BRIDGE_DEBUG"):
            sys.stderr.write("krita_8bfhost_bridge: %s\n" % message)

    def _report(self, parent, result, fallback):
        box = QMessageBox(parent)
        box.setWindowTitle(MENU_TITLE)
        box.setText(result.message or fallback)
        if result.log:
            box.setDetailedText("\n".join(result.log[-200:]))
        _exec(box)

    def repeat_last(self):
        if self.last_id:
            self.run_filter(self.last_id, show_ui=False)

    def run_filter(self, filter_id, show_ui=True):
        entry = self.catalog.find(filter_id)
        parent = self._window()
        if entry is None:
            QMessageBox.warning(parent, MENU_TITLE, "That filter is no longer installed.")
            return
        try:
            executable = host.require_executable(self.settings.host_path)
        except host.HostError as exc:
            QMessageBox.warning(parent, MENU_TITLE, str(exc))
            return
        job_dir = tempfile.mkdtemp(prefix="krita_8bfhost_bridge-")
        try:
            try:
                job = krita_bridge.capture(self.krita, job_dir)
            except krita_bridge.BridgeError as exc:
                QMessageBox.information(parent, MENU_TITLE, str(exc))
                return
            preset = self.presets.existing(filter_id) if self.presets else None
            command = host.run_command(
                executable,
                self.settings.folders,
                filter_id,
                job.input_path,
                job.output_path,
                dialog=show_ui or preset is None,
                preset=preset,
                save_preset=self.presets.path(filter_id) if self.presets else None,
                mask=job.mask_path,
                rect=job.rect,
                foreground=job.foreground,
                background=job.background,
                resolution=job.resolution,
                allow_8bit_fallback=self.settings.allow_8bit_fallback,
            )
            self._log("running %s" % " ".join(command))
            progress = FilterProgress(parent, entry.name)
            try:
                result = host.run(
                    command,
                    pump=QApplication.processEvents,
                    cancelled=progress.cancelled,
                    cwd=job_dir,
                )
            finally:
                progress.close()
            for line in result.log:
                self._log(line)
            if result.status == "cancelled":
                return
            if not result.ok:
                self._report(parent, result, "The filter failed.")
                return
            layer_name = None
            if self.settings.apply_mode == settings_module.APPLY_NEW_LAYER:
                layer_name = "%s (%s)" % (job.node.name(), entry.name)
            try:
                krita_bridge.apply(job, layer_name)
            except krita_bridge.BridgeError as exc:
                QMessageBox.warning(parent, MENU_TITLE, str(exc))
                return
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

        self.last_id = filter_id
        self.krita.writeSetting(settings_module.GROUP, "last_filter", filter_id)
        self._update_repeat()

    def show_about(self, filter_id):
        entry = self.catalog.find(filter_id)
        parent = self._window()
        if entry is None:
            return
        if not entry.has_about_box:
            QMessageBox.information(parent, MENU_TITLE, "%s has no About box." % entry.name)
            return
        try:
            executable = host.require_executable(self.settings.host_path)
        except host.HostError as exc:
            QMessageBox.warning(parent, MENU_TITLE, str(exc))
            return
        result = host.run(
            host.about_command(executable, self.settings.folders, filter_id),
            pump=QApplication.processEvents,
        )
        if not result.ok and result.status != "cancelled":
            self._report(parent, result, "Could not show the About box.")

    def check_setup(self, settings):
        executable = host.find_executable(settings.host_path)
        if not executable:
            return "8bf-host was not found on PATH.\n\nDownload it from %s." % host.DOWNLOAD_URL
        result = host.run(
            host.doctor_command(executable, settings.folders), pump=QApplication.processEvents
        )
        text = (result.stdout + "\n".join(result.log)).strip()
        return "%s\n\n%s" % (executable, text or result.message)

    def show_settings(self):
        dialog = SettingsDialog(
            self.settings,
            self.catalog,
            self._window(),
            on_rescan=lambda settings: self._scan(rescan=True, settings=settings),
            on_about=self.show_about,
            on_check=self.check_setup,
        )
        if _exec(dialog):
            self.settings = dialog.current_settings()
            settings_module.save(self.settings, self.backend)
        self._scan()
