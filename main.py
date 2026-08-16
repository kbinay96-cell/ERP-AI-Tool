"""
main.py

Entry point for the Coding AI Desktop Tool.
No business logic here - sirf QApplication start karta hai aur MainWindow dikhata hai.

Run karne ka tareeka (ERP-AI-Tool folder ke ANDAR se):
    python main.py
"""

import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "coding_ai.log")


def _configure_logging() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
    )


def main() -> None:
    _configure_logging()
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()