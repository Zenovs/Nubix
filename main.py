"""
Nubix - Cloud Sync Manager for Ubuntu
Entry point for the application.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

# Ensure the package root is importable when running as a script
sys.path.insert(0, str(Path(__file__).parent))


def main() -> int:
    """Application entry point."""
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Nubix")
    app.setApplicationVersion("0.2.9")
    app.setOrganizationName("Nubix")
    app.setQuitOnLastWindowClosed(False)  # Keep running in system tray

    # Set up top-level exception handler
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

    # Start the application
    from nubix.app import NubixApp

    nubix = NubixApp(app)
    nubix.start(background="--background" in sys.argv)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
