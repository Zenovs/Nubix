"""Wizard provider selection page — all rclone backends."""

from __future__ import annotations

from PySide6.QtCore import Property, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWizardPage,
)

from nubix.providers import list_providers


class ProviderSelectPage(QWizardPage):
    _provider_id_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Choose a Cloud Provider")
        self.setSubTitle("Select the service you want to connect to.")

        self._providers = list_providers()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Search bar ──
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search providers…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        # ── Provider list ──
        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background: #1E1E32; border: 1px solid #2E2E50;"
            " border-radius: 10px; padding: 4px; outline: none; }"
            "QListWidget::item { padding: 10px 14px; border-radius: 7px;"
            " margin: 2px 4px; color: #E2E2F0; font-size: 13px; }"
            "QListWidget::item:selected { background: #7C5CFC; color: #FFFFFF; font-weight: 600; }"
            "QListWidget::item:hover:!selected { background: #252542; }"
        )
        self._list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

        # ── Selection info ──
        self._info_label = QLabel("← Select a provider from the list")
        self._info_label.setStyleSheet("color: #8888AA; font-size: 12px;")
        layout.addWidget(self._info_label)

        self._populate(self._providers)

        # changedSignal must belong to self (the page), not to a child widget
        self.registerField("provider_id*", self, "provider_id", self._provider_id_changed)

    def _populate(self, providers):
        self._list.clear()
        for p in providers:
            item = QListWidgetItem(f"{p.icon}   {p.display_name}")
            item.setData(Qt.ItemDataRole.UserRole, p.provider_id)
            self._list.addItem(item)

    def _filter(self, text: str):
        filtered = [
            p
            for p in self._providers
            if text.lower() in p.display_name.lower() or text.lower() in p.provider_id.lower()
        ]
        self._populate(filtered)

    def _on_selection_changed(self, row: int):
        if row < 0:
            self._info_label.setText("← Select a provider from the list")
            return
        item = self._list.item(row)
        if not item:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        from nubix.providers import get_provider

        try:
            p = get_provider(pid)
            self._info_label.setText(
                f"<b>{p.icon} {p.display_name}</b>  ·  "
                f"<span style='color:#8888AA'>rclone type: <code>{p.get_rclone_type()}</code></span>"
            )
        except Exception:
            pass
        self._provider_id_changed.emit(self._get_provider_id())
        self.completeChanged.emit()

    def _get_provider_id(self) -> str:
        item = self._list.currentItem()
        if not item:
            return ""
        return item.data(Qt.ItemDataRole.UserRole) or ""

    def _set_provider_id(self, val: str):
        pass

    # Must be a Qt Property (not Python property) so QWizard.field() can read it
    provider_id = Property(str, _get_provider_id, _set_provider_id, notify=_provider_id_changed)

    def isComplete(self) -> bool:
        return bool(self._get_provider_id())
