"""Desktop entry point."""

from __future__ import annotations

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from core.branding import APP_NAME
from desktop.launch import LaunchWindow
from pathlib import Path


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)
    icon = Path(__file__).resolve().parents[1] / "vantage_core_icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = LaunchWindow()
    window.show()
    return app.exec()
