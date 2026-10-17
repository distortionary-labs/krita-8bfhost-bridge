"""Qt dialogs: settings, filter list, progress and text output."""

import copy

from . import host
from . import settings as settings_module
from .qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    Qt,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    enum,
)

APPLY_MODES = [
    (settings_module.APPLY_NEW_LAYER, "Into a new layer above the active layer"),
    (settings_module.APPLY_IN_PLACE, "Into the active layer (cannot be undone)"),
]


def _exec(dialog):
    return dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()


class FilterProgress:
    """A modal busy dialog whose Cancel button stops the filter.

    8bf-host does not report progress to a pipe, so the bar only shows
    that the filter is running. The filter's own window belongs to the
    8bf-host process and may open behind Krita.
    """

    def __init__(self, parent, title):
        self.dialog = QProgressDialog(
            "Running %s… Its window may open behind Krita." % title, "Cancel", 0, 0, parent
        )
        self.dialog.setWindowTitle("Photoshop Filter")
        self.dialog.setWindowModality(enum(Qt, "WindowModality", "WindowModal"))
        self.dialog.setMinimumDuration(0)
        self.dialog.setAutoClose(False)
        self.dialog.setAutoReset(False)
        self.dialog.setValue(0)

    def cancelled(self):
        return self.dialog.wasCanceled()

    def close(self):
        self.dialog.close()


def show_text(parent, title, text):
    """Show program output in a scrollable, fixed-width text box."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(720, 360)
    box = QPlainTextEdit(text)
    box.setReadOnly(True)
    box.setStyleSheet("font-family: monospace;")
    buttons = QDialogButtonBox(enum(QDialogButtonBox, "StandardButton", "Close"))
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addWidget(box)
    layout.addWidget(buttons)
    _exec(dialog)


class _PathField(QWidget):
    def __init__(self, value, file_filter="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(value)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        layout.addWidget(self.edit)
        layout.addWidget(browse)
        self.file_filter = file_filter

    def _browse(self):
        path, _selected = QFileDialog.getOpenFileName(
            self, "Choose a file", self.edit.text(), self.file_filter
        )
        if path:
            self.edit.setText(path)

    def text(self):
        return self.edit.text().strip()


class SettingsDialog(QDialog):
    """Edit settings and browse the filters 8bf-host found.

    ``on_rescan(settings)`` reloads the catalog with the settings as they
    are in the dialog; ``on_about(filter_id)`` shows a filter's About box;
    ``on_check(settings)`` returns the output of ``8bf-host doctor``.
    """

    def __init__(
        self, settings, catalog, parent=None, on_rescan=None, on_about=None, on_check=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Photoshop Filters (8bf)")
        self.resize(680, 520)
        self.settings = copy.deepcopy(settings)
        self.catalog = catalog
        self.on_rescan = on_rescan
        self.on_about = on_about
        self.on_check = on_check

        tabs = QTabWidget()
        tabs.addTab(self._host_tab(), "8bf-host")
        tabs.addTab(self._filters_tab(), "Filters")
        tabs.addTab(self._folders_tab(), "Folders")

        buttons = QDialogButtonBox(
            enum(QDialogButtonBox, "StandardButton", "Ok")
            | enum(QDialogButtonBox, "StandardButton", "Cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self._refresh_filters()

    # 8bf-host tab ----------------------------------------------------------

    def _host_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        intro = QLabel(
            "Filters run in 8bf-host, a separate program. Download it from "
            '<a href="{url}">{url}</a> and set its location below, or leave the field '
            "empty to look for it on PATH. On Linux, Windows filters run under Wine; "
            "8bf-host's own documentation covers that setup.".format(url=host.DOWNLOAD_URL)
        )
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(True)
        form.addRow(intro)

        self.host_path = _PathField(self.settings.host_path)
        self.host_path.edit.setPlaceholderText(host.find_executable("") or "not found")
        form.addRow("8bf-host program:", self.host_path)
        check = QPushButton("Check Setup")
        check.setToolTip("Runs 8bf-host doctor")
        check.clicked.connect(self._check)
        row = QHBoxLayout()
        row.addWidget(check)
        row.addStretch(1)
        form.addRow("", row)

        self.apply_mode = QComboBox()
        for value, label in APPLY_MODES:
            self.apply_mode.addItem(label, value)
        applies = [v for v, _ in APPLY_MODES]
        self.apply_mode.setCurrentIndex(
            applies.index(self.settings.apply_mode) if self.settings.apply_mode in applies else 0
        )
        form.addRow("Apply results:", self.apply_mode)

        self.fallback = QCheckBox("Run 8-bit-only filters on 16-bit layers via an 8-bit copy")
        self.fallback.setChecked(self.settings.allow_8bit_fallback)
        form.addRow("", self.fallback)
        return page

    def _check(self):
        if self.on_check:
            show_text(self, "8bf-host doctor", self.on_check(self.current_settings()))

    # Filters tab ------------------------------------------------------------

    def _filters_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Filter", "Runs", "File"])
        self.tree.setColumnWidth(0, 220)
        self.tree.setColumnWidth(1, 220)
        self.status = QLabel()
        self.status.setWordWrap(True)
        row = QHBoxLayout()
        rescan = QPushButton("Rescan")
        rescan.clicked.connect(self._rescan)
        about = QPushButton("About Filter…")
        about.clicked.connect(self._about)
        row.addWidget(rescan)
        row.addWidget(about)
        row.addStretch(1)
        layout.addWidget(self.tree)
        layout.addWidget(self.status)
        layout.addLayout(row)
        return page

    def _refresh_filters(self):
        self.tree.clear()
        for category, entries in sorted(self.catalog.by_category().items()):
            parent = QTreeWidgetItem([category])
            self.tree.addTopLevelItem(parent)
            for entry in entries:
                item = QTreeWidgetItem(
                    [entry.name, entry.runs or "cannot run: %s" % entry.problem, entry.path]
                )
                item.setData(0, enum(Qt, "ItemDataRole", "UserRole"), entry.id)
                parent.addChild(item)
            parent.setExpanded(True)
        if self.catalog.error:
            self.status.setText(self.catalog.error)
            return
        count = len(self.catalog.filters)
        text = "%d filter%s found." % (count, "" if count == 1 else "s")
        if self.catalog.problems:
            text += " Problems:\n" + "\n".join(
                "%s: %s" % (path, error) for path, error in self.catalog.problems[:10]
            )
        self.status.setText(text)

    def _rescan(self):
        if self.on_rescan:
            self.on_rescan(self.current_settings())
        self._refresh_filters()

    def _about(self):
        item = self.tree.currentItem()
        filter_id = item.data(0, enum(Qt, "ItemDataRole", "UserRole")) if item else None
        if filter_id and self.on_about:
            self.on_about(filter_id)

    # Folders tab -----------------------------------------------------------

    def _folders_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(
            "Folders searched (with subfolders) for .8bf files and macOS .plugin bundles, "
            "in addition to the ones 8bf-host searches on its own:"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.folder_list = QListWidget()
        self.folder_list.addItems(self.settings.folders)
        row = QHBoxLayout()
        add = QPushButton("Add…")
        add.clicked.connect(self._add_folder)
        remove = QPushButton("Remove")
        remove.clicked.connect(self._remove_folder)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        layout.addWidget(self.folder_list)
        layout.addLayout(row)
        return page

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose a plug-in folder")
        if folder and folder not in self._folder_values():
            self.folder_list.addItem(folder)

    def _remove_folder(self):
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))

    def _folder_values(self):
        return [self.folder_list.item(i).text() for i in range(self.folder_list.count())]

    # Result ----------------------------------------------------------------

    def current_settings(self):
        """The settings as currently edited in the dialog."""
        settings = copy.deepcopy(self.settings)
        settings.host_path = self.host_path.text()
        settings.folders = self._folder_values()
        settings.apply_mode = self.apply_mode.currentData()
        settings.allow_8bit_fallback = self.fallback.isChecked()
        return settings
