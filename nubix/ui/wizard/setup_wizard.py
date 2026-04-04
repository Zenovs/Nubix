"""Main setup wizard for adding a new cloud connection."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWizard

from nubix.core.credential_vault import CredentialVault
from nubix.core.rclone_engine import RcloneEngine
from nubix.core.remote_registry import RemoteRegistry
from nubix.core.sync_manager import SyncManager
from nubix.core.sync_job import SyncMode
from nubix.providers import get_provider
from nubix.ui.wizard.pages.auth_page import AuthPage
from nubix.ui.wizard.pages.confirmation_page import ConfirmationPage
from nubix.ui.wizard.pages.local_folder_page import LocalFolderPage
from nubix.ui.wizard.pages.provider_select_page import ProviderSelectPage
from nubix.ui.wizard.pages.sync_mode_page import SyncModePage
from nubix.ui.wizard.pages.welcome_page import WelcomePage

logger = logging.getLogger(__name__)

PAGE_WELCOME = 0
PAGE_PROVIDER = 1
PAGE_AUTH = 2
PAGE_LOCAL_FOLDER = 3
PAGE_SYNC_MODE = 4
PAGE_CONFIRMATION = 5


class SetupWizard(QWizard):
    """Step-by-step wizard for adding a new cloud connection."""

    def __init__(
        self,
        registry: RemoteRegistry,
        vault: CredentialVault,
        engine: RcloneEngine,
        sync_manager: SyncManager | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._registry = registry
        self._vault = vault
        self._engine = engine
        self._sync = sync_manager

        # Pass the resolved rclone binary to AuthPage so it uses the right one
        rclone_binary = getattr(engine, "_binary", None) or shutil.which("rclone") or "rclone"
        self._auth_page = AuthPage(binary=rclone_binary)

        self.setWindowTitle("Add Cloud Connection — Nubix")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(560, 420)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)

        self.setPage(PAGE_WELCOME, WelcomePage())
        self.setPage(PAGE_PROVIDER, ProviderSelectPage())
        self.setPage(PAGE_AUTH, self._auth_page)
        self.setPage(PAGE_LOCAL_FOLDER, LocalFolderPage())
        self.setPage(PAGE_SYNC_MODE, SyncModePage())
        self.setPage(PAGE_CONFIRMATION, ConfirmationPage())

        self.accepted.connect(self._on_accepted)

    def _on_accepted(self):
        """Called when the user clicks Finish. Saves the remote and optionally starts sync."""
        provider_id = self.field("provider_id") or ""
        local_path = self.field("local_path") or ""
        sync_mode_value = self.field("sync_mode_value") or SyncMode.FULL.value
        credentials = self._auth_page.get_credentials()

        try:
            provider = get_provider(provider_id)
        except Exception as e:
            logger.error("Unknown provider %s: %s", provider_id, e)
            QMessageBox.critical(self, "Error", f"Unknown provider: {provider_id}")
            return

        # Ensure local folder exists
        lp = Path(local_path)
        lp.mkdir(parents=True, exist_ok=True)

        # Derive a unique remote_id
        remote_id = f"{provider_id}_{str(uuid.uuid4())[:6]}"

        # Configure rclone remote (type is the first element of config_args)
        config_args = provider.get_rclone_config_args(credentials)
        success = self._engine.configure_remote(remote_id, config_args)
        if not success:
            logger.error("rclone remote configuration failed for %s", remote_id)
            QMessageBox.critical(
                self,
                "Configuration Error",
                f"Failed to configure the {provider.display_name} remote.\n\n"
                "Make sure rclone is installed and the credentials are correct.",
            )
            return

        # Store credentials in vault
        for key, value in credentials.items():
            if value:
                self._vault.store(remote_id, key, str(value))

        # Register remote — emits remote_added, which adds the card to the dashboard
        rc = self._registry.add_remote(
            {
                "remote_id": remote_id,
                "display_name": provider.display_name,
                "provider_type": provider_id,
                "local_path": local_path,
                "remote_path": "",
                "sync_mode": sync_mode_value,
                "is_enabled": True,
            }
        )

        logger.info("Remote %s added successfully", remote_id)

        # Optionally start sync immediately
        conf_page = self.page(PAGE_CONFIRMATION)
        if isinstance(conf_page, ConfirmationPage) and conf_page.should_start_now():
            if self._sync is not None:
                logger.info("Starting immediate sync for %s", remote_id)
                self._sync.start_job(rc.to_sync_job())
