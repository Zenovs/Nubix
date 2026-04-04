"""Remotes/connections management tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nubix.core.remote_registry import RemoteConfig, RemoteRegistry


class RemotesTab(QWidget):
    def __init__(self, registry: RemoteRegistry, parent=None):
        super().__init__(parent)
        self._registry = registry
        self._build_ui()
        self._load()
        registry.remote_added.connect(self._on_remote_added)
        registry.remote_removed.connect(self._on_remote_removed)

    def _build_ui(self):
        layout = QHBoxLayout(self)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

        buttons = QVBoxLayout()
        self._btn_add = QPushButton("Add…")
        self._btn_add.clicked.connect(self._add)
        buttons.addWidget(self._btn_add)

        self._btn_remove = QPushButton("Remove")
        self._btn_remove.setEnabled(False)  # disabled until something is selected
        self._btn_remove.clicked.connect(self._remove)
        buttons.addWidget(self._btn_remove)

        buttons.addStretch()
        layout.addLayout(buttons)

    def _load(self):
        self._list.clear()
        for rc in self._registry.list_remotes():
            self._add_item(rc)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _add_item(self, rc: RemoteConfig):
        item = QListWidgetItem(f"{rc.display_name}  ({rc.local_path})")
        item.setData(Qt.ItemDataRole.UserRole, rc.remote_id)
        self._list.addItem(item)

    def _on_selection_changed(self, current, previous):
        self._btn_remove.setEnabled(current is not None)

    def _on_remote_added(self, rc: RemoteConfig):
        self._add_item(rc)

    def _on_remote_removed(self, remote_id: str):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == remote_id:
                self._list.takeItem(i)
                return

    def _add(self):
        # Trigger wizard from parent window
        parent = self.window()
        if hasattr(parent, "open_wizard"):
            parent.open_wizard()

    def _remove(self):
        item = self._list.currentItem()
        if not item:
            return
        remote_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            rc = self._registry.get_remote(remote_id)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not find connection: {e}")
            return
        reply = QMessageBox.question(
            self,
            "Remove Connection",
            f"Remove '{rc.display_name}'?\n\nLocal files will NOT be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._registry.remove_remote(remote_id)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to remove connection: {e}")
