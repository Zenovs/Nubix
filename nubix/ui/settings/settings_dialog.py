"""Settings dialog with tabbed interface."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QVBoxLayout,
)

from nubix.core.bandwidth_controller import BandwidthController
from nubix.core.config_manager import ConfigManager
from nubix.core.remote_registry import RemoteRegistry
from nubix.core.scheduler import Scheduler


class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(
        self,
        config: ConfigManager,
        registry: RemoteRegistry,
        scheduler: Scheduler,
        bandwidth: BandwidthController,
        updater=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Nubix Settings")
        self.setMinimumSize(640, 500)

        self._config = config
        self._pending: dict = {}

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, 1)

        # Import here to avoid circular at module load time
        from nubix.ui.settings.general_tab import GeneralTab
        from nubix.ui.settings.bandwidth_tab import BandwidthTab
        from nubix.ui.settings.scheduler_tab import SchedulerTab
        from nubix.ui.settings.remotes_tab import RemotesTab
        from nubix.ui.settings.update_tab import UpdateTab

        self._general_tab = GeneralTab(config)
        self._bandwidth_tab = BandwidthTab(bandwidth)
        self._scheduler_tab = SchedulerTab(registry, scheduler)
        self._remotes_tab = RemotesTab(registry)

        self._tabs.addTab(self._general_tab, "⚙  General")
        self._tabs.addTab(self._bandwidth_tab, "📶  Bandwidth")
        self._tabs.addTab(self._scheduler_tab, "🕐  Scheduler")
        self._tabs.addTab(self._remotes_tab, "☁  Connections")

        if updater is not None:
            self._update_tab = UpdateTab(updater)
            self._tabs.addTab(self._update_tab, "🔄  Updates")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply(self):
        self._general_tab.save()
        self._bandwidth_tab.save()
        self._scheduler_tab.save()
        self.accept()
