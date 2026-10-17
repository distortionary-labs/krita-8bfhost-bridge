"""Qt imports for Krita 5 (PyQt5) and Krita 6 (PyQt6)."""

try:
    from PyQt5.QtCore import QByteArray, QStandardPaths, Qt
    from PyQt5.QtWidgets import (
        QAction,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QProgressDialog,
        QPushButton,
        QTabWidget,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    QT6 = False
except ImportError:  # pragma: no cover - Krita 6
    from PyQt6.QtCore import QByteArray, QStandardPaths, Qt
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QProgressDialog,
        QPushButton,
        QTabWidget,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    QT6 = True


def enum(owner, scope, name):
    """Return an enum value by its scoped name on PyQt6, flat name on PyQt5."""
    if QT6:
        return getattr(getattr(owner, scope), name)
    return getattr(owner, name)


__all__ = [
    "QAction",
    "QApplication",
    "QByteArray",
    "QCheckBox",
    "QComboBox",
    "QDialog",
    "QDialogButtonBox",
    "QFileDialog",
    "QFormLayout",
    "QGroupBox",
    "QHBoxLayout",
    "QLabel",
    "QLineEdit",
    "QListWidget",
    "QMenu",
    "QMessageBox",
    "QPlainTextEdit",
    "QProgressDialog",
    "QPushButton",
    "QStandardPaths",
    "QTabWidget",
    "QTreeWidget",
    "QTreeWidgetItem",
    "QVBoxLayout",
    "QWidget",
    "Qt",
    "QT6",
    "enum",
]
