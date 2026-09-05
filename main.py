"""Clapper Sorting application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    """Create and start the desktop application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Clapper Sorting")
    app.setOrganizationName("Clapper Sorting")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
