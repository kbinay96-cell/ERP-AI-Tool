"""
caretaker_gui.py

PyQt6 Single-Window GUI for the Medical ERP v2 Autonomous Caretaker.
Connects directly to caretaker_orchestrator.py FastAPI endpoints.
"""
import sys
import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QSplitter, QMessageBox, QLineEdit
)
from PyQt6.QtCore import Qt


class CaretakerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ERP-AI Caretaker - Single Window Patch Dashboard")
        self.resize(1100, 700)
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Server URL bar
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Orchestrator URL:"))
        self.url_input = QLineEdit("http://127.0.0.1:8000")
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)

        # Splitter for Text Areas
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: Patch Input
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("<b>1. Paste Code Blocks / Patch Content:</b>"))
        self.patch_input = QTextEdit()
        self.patch_input.setPlaceholderText("Paste markdown code blocks or unified diff patches here...")
        left_layout.addWidget(self.patch_input)
        splitter.addWidget(left_widget)

        # Right Panel: Preview & Test Results Output
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("<b>2. Preview Diff / Execution Logs:</b>"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        right_layout.addWidget(self.log_output)
        splitter.addWidget(right_widget)

        main_layout.addWidget(splitter)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_preview = QPushButton("Preview Patch Diff")
        self.btn_preview.clicked.connect(self.preview_diff)
        btn_layout.addWidget(self.btn_preview)

        self.btn_apply = QPushButton("Apply & Run Pytest Sandbox")
        self.btn_apply.setStyleSheet("background-color: #2b78e4; color: white; font-weight: bold;")
        self.btn_apply.clicked.connect(self.apply_and_run)
        btn_layout.addWidget(self.btn_apply)

        main_layout.addLayout(btn_layout)

    def preview_diff(self):
        text = self.patch_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Please paste some code blocks first.")
            return

        base_url = self.url_input.text().rstrip("/")
        try:
            resp = requests.post(f"{base_url}/preview_code_blocks", json={"raw_text": text})
            if resp.status_code == 200:
                data = resp.json()
                self.log_output.clear()
                self.log_output.append("=== DIFF PREVIEW ===\n")
                for item in data:
                    self.log_output.append(f"File: {item.get('file_path')}\n{item.get('diff')}\n{'-'*40}")
            else:
                self.log_output.setText(f"Error ({resp.status_code}): {resp.text}")
        except Exception as e:
            self.log_output.setText(f"Connection Failed: {e}\nEnsure caretaker_orchestrator is running!")

    def apply_and_run(self):
        text = self.patch_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Please paste some code blocks first.")
            return

        base_url = self.url_input.text().rstrip("/")
        try:
            resp = requests.post(
                f"{base_url}/apply_and_run_sandbox",
                json={"raw_text": text, "pytest_args": "-q"}
            )
            if resp.status_code == 200:
                data = resp.json()
                self.log_output.clear()
                self.log_output.append("=== APPLY RESULTS ===")
                for r in data.get("apply_results", []):
                    self.log_output.append(str(r))
                
                pytest_res = data.get("pytest")
                if pytest_res:
                    self.log_output.append("\n=== PYTEST SANDBOX EXECUTION ===")
                    self.log_output.append(f"Exit Code: {pytest_res.get('returncode')}")
                    self.log_output.append(pytest_res.get("stdout") or "")
                    self.log_output.append(pytest_res.get("stderr") or "")
            else:
                self.log_output.setText(f"Error ({resp.status_code}): {resp.text}")
        except Exception as e:
            self.log_output.setText(f"Connection Failed: {e}\nEnsure caretaker_orchestrator is running!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = CaretakerGUI()
    gui.show()
    sys.exit(app.exec())
