"""
ui/main_window.py

Modern AI-chat style main window for ERP-AI-Tool.
Design goal:
- पुराना basic form-style look नहीं
- Claude/Gemini जैसा modern workspace
- left session sidebar
- center chat panel
- right utility panel
- dark/light theme support
- existing workers/storage/analyzers reuse
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime

from dotenv import load_dotenv
from PyQt6.QtCore import Qt, QSettings, QTimer, QUrl, QEvent
from PyQt6.QtGui import QAction, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QSplitter,
    QTextEdit,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storage.chat_storage import ChatStorage
from ui.chat_formatter import (
    DEFAULT_FONT_SIZE_PT,
    MAX_FONT_SIZE_PT,
    MIN_FONT_SIZE_PT,
    format_message_html,
    get_chat_area_background,
)
from ui.query_worker import MAX_HISTORY_MESSAGES, QueryWorker
from ui.scan_worker import ScanWorker
from code_block_applier import apply_all_blocks
# OpenHands Agent ko safely import karte hain (agar environment mein na ho toh bhi UI crash na ho)
try:
    from ui.openhands_worker import OpenHandsWorker
    _OPENHANDS_AVAILABLE = True
except ImportError:
    _OPENHANDS_AVAILABLE = False

from ai_financial_ledger_audit import run_audit
from ai_inventory_allocator import evaluate_inventory_allocation
from ai_production_job_scheduler import schedule_jobs
from erp_inventory_risk_engine import analyze_warehouse_risk
from purchase_requisition_analyzer import analyze_purchase_requisition

load_dotenv()

logger = logging.getLogger(__name__)

WINDOW_TITLE = "ERP AI Tool - AI Software Workstation"
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 780

MEMORY_FILE_NAME = "erp_memory.json"

TREE_IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "logs",
    "tmp",
    ".cache",
}


DARK_QSS = """
#ModernRoot {
    background-color: #0f1117;
}

#Sidebar,
#UtilityDock {
    background-color: #151823;
    color: #d7dae5;
}

#CenterPanel {
    background-color: #0f1117;
}

#TopBar {
    background-color: #151823;
    border: 1px solid #232634;
    border-radius: 14px;
}

#TitleLabel {
    color: #f2f4fb;
    font-size: 13px;
    font-weight: 700;
}

#SubtitleLabel {
    color: #9aa1b5;
    font-size: 11px;
}

#PrimaryButton {
    background-color: #4f7cff;
    color: white;
    border: none;
    padding: 8px 14px;
    border-radius: 10px;
    font-weight: 600;
}

#PrimaryButton:hover {
    background-color: #658cff;
}

#PrimaryButton:disabled {
    background-color: #2b3040;
    color: #7f8698;
}

#IconButton {
    background-color: transparent;
    border: 1px solid #2a2f3f;
    border-radius: 10px;
    padding: 6px 9px;
    color: #d7dae5;
}

#IconButton:hover {
    background-color: #1d2230;
}

#SearchBox,
#ComposerInput {
    background-color: #1b1f2c;
    border: 1px solid #2a2f3f;
    border-radius: 10px;
    padding: 8px 10px;
    color: #e8eaf2;
    selection-background-color: #4f7cff;
}

#SessionList {
    background-color: transparent;
    border: none;
    font-size: 13px;
    color: #d7dae5;
    outline: none;
}

#SessionList::item {
    padding: 8px 10px;
    border-radius: 8px;
    margin: 2px 6px;
    color: #d7dae5;
}

#SessionList::item:hover {
    background-color: #1d2230;
}

#SessionList::item:selected {
    background-color: #2b3044;
    color: white;
}

#ChatLog {
    border: none;
    font-size: 13px;
}

#AgentLogs,
#FileTree {
    background-color: #11141d;
    color: #d7dae5;
    border: none;
}

QDockWidget {
    color: #d7dae5;
}

QDockWidget::title {
    background-color: #10131c;
    padding: 8px;
}

QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    color: #9aa1b5;
    padding: 8px 12px;
    border: none;
}

QTabBar::tab:selected {
    color: white;
    border-bottom: 2px solid #4f7cff;
}

QMenuBar {
    background-color: #151823;
    color: #d7dae5;
}

QMenuBar::item:selected {
    background-color: #2b3044;
}

QMenu {
    background-color: #181c29;
    color: #d7dae5;
    border: 1px solid #262b3b;
}

QMenu::item:selected {
    background-color: #2b3044;
}

QStatusBar {
    background-color: #10131c;
    color: #9aa1b5;
}

QProgressBar {
    background-color: #1b1f2c;
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #4f7cff;
    border-radius: 6px;
}

QLabel {
    color: #d7dae5;
}

QTreeWidget::item:selected {
    background-color: #2b3044;
}
"""


LIGHT_QSS = """
#ModernRoot {
    background-color: #f5f7fb;
}

#Sidebar,
#UtilityDock {
    background-color: #ffffff;
    color: #1f2430;
}

#CenterPanel {
    background-color: #f5f7fb;
}

#TopBar {
    background-color: #ffffff;
    border: 1px solid #dfe3ee;
    border-radius: 14px;
}

#TitleLabel {
    color: #101828;
    font-size: 13px;
    font-weight: 700;
}

#SubtitleLabel {
    color: #667085;
    font-size: 11px;
}

#PrimaryButton {
    background-color: #2f6fed;
    color: white;
    border: none;
    padding: 8px 14px;
    border-radius: 10px;
    font-weight: 600;
}

#PrimaryButton:hover {
    background-color: #4a82f0;
}

#PrimaryButton:disabled {
    background-color: #cdd6e8;
    color: #7a8194;
}

#IconButton {
    background-color: white;
    border: 1px solid #d8ddea;
    border-radius: 10px;
    padding: 6px 9px;
    color: #1f2430;
}

#IconButton:hover {
    background-color: #eef2fb;
}

#SearchBox,
#ComposerInput {
    background-color: white;
    border: 1px solid #d8ddea;
    border-radius: 10px;
    padding: 8px 10px;
    color: #101828;
    selection-background-color: #2f6fed;
}

#SessionList {
    background-color: transparent;
    border: none;
    font-size: 13px;
    color: #1f2430;
    outline: none;
}

#SessionList::item {
    padding: 8px 10px;
    border-radius: 8px;
    margin: 2px 6px;
    color: #1f2430;
}

#SessionList::item:hover {
    background-color: #eef2fb;
}

#SessionList::item:selected {
    background-color: #d9e4ff;
    color: #101828;
}

#ChatLog {
    border: none;
    font-size: 13px;
}

#AgentLogs,
#FileTree {
    background-color: #fbfcff;
    color: #1f2430;
    border: none;
}

QDockWidget {
    color: #1f2430;
}

QDockWidget::title {
    background-color: #eef1f8;
    padding: 8px;
}

QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    color: #667085;
    padding: 8px 12px;
    border: none;
}

QTabBar::tab:selected {
    color: #101828;
    border-bottom: 2px solid #2f6fed;
}

QMenuBar {
    background-color: #ffffff;
    color: #1f2430;
}

QMenuBar::item:selected {
    background-color: #d9e4ff;
}

QMenu {
    background-color: #ffffff;
    color: #1f2430;
    border: 1px solid #dfe3ee;
}

QMenu::item:selected {
    background-color: #d9e4ff;
}

QStatusBar {
    background-color: #eef1f8;
    color: #667085;
}

QProgressBar {
    background-color: #e6eaf3;
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #2f6fed;
    border-radius: 6px;
}

QLabel {
    color: #1f2430;
}

QTreeWidget::item:selected {
    background-color: #d9e4ff;
}
"""


class MainWindow(QMainWindow):
    """Modern ERP-AI-Tool main window."""

    def __init__(self) -> None:
        super().__init__()

        self._project_root: str | None = None
        self._scan_worker: ScanWorker | None = None
        self._query_worker: QueryWorker | None = None
        self._agent_worker = None

        self._chat_history: list[dict] = []
        self._display_messages: list[tuple[str, str]] = []
        self._last_query_text: str = ""
        self._stop_requested: bool = False

        self._chat_font_size: int = DEFAULT_FONT_SIZE_PT
        self._theme: str = "dark"

        self.storage = ChatStorage()
        self._active_session_id: str | None = None

        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.setObjectName("ModernRoot")

        self._build_ui()
        self._connect_signals()
        self._load_initial_session()
        self._apply_theme()
        self._refresh_action_states()

        self._load_last_project_folder()
        self._auto_load_blueprint()
        self._last_agent_text: str = ""

        # Status bar mein live date/time
        self.lbl_datetime = QLabel("")
        self.lbl_datetime.setObjectName("SubtitleLabel")
        self.statusBar().addPermanentWidget(self.lbl_datetime)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_statusbar_datetime)
        self._timer.start(1000)
        self._update_statusbar_datetime()

        # Agent processing ke dauraan live "kaam ho raha hai" indicator
        self._agent_elapsed_seconds: int = 0
        self._agent_tick_timer = QTimer(self)
        self._agent_tick_timer.timeout.connect(self._on_agent_tick)
        
        # Drag & Drop blueprint upload enable karo
        self.txt_chat_log.setAcceptDrops(True)
        self.txt_chat_log.installEventFilter(self)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Central panel now embeds the utility tabs (Files / Agent Logs / Apply Code)
        # so we only add the left sidebar as a dock. This produces a single cohesive
        # main window where chat and agent/tools live in one view.
        self.setCentralWidget(self._build_center_panel())

        self.dock_sidebar = self._build_sidebar_dock()
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_sidebar)

        # Do not create a right utility dock anymore; utility tabs are embedded
        # inside the center panel below the chat area.
        self._build_menu_bar()
        self.statusBar().showMessage("Ready. Select a project folder to begin.")

    def _build_menu_bar(self) -> None:
        view_menu = self.menuBar().addMenu("&View")
        # Only add sidebar toggle (utility tabs are now embedded in center panel)
        view_menu.addAction(self.dock_sidebar.toggleViewAction())
        view_menu.addSeparator()

        self.action_dark_mode = QAction("Dark Mode", self, checkable=True)
        self.action_dark_mode.setChecked(self._theme == "dark")
        self.action_dark_mode.toggled.connect(self._on_toggle_theme)
        view_menu.addAction(self.action_dark_mode)

    def _build_sidebar_dock(self) -> QDockWidget:
        dock = QDockWidget("Chats", self)
        dock.setObjectName("Sidebar")
        dock.setMinimumWidth(250)

        container = QWidget()
        container.setObjectName("SidebarContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.btn_new_chat = QPushButton("+ New Chat")
        self.btn_new_chat.setObjectName("PrimaryButton")
        self.btn_new_chat.setToolTip("Start a fresh conversation")
        layout.addWidget(self.btn_new_chat)

        self.txt_session_search = QLineEdit()
        self.txt_session_search.setObjectName("SearchBox")
        self.txt_session_search.setPlaceholderText("Search chats...")
        self.txt_session_search.setClearButtonEnabled(True)
        layout.addWidget(self.txt_session_search)

        self.list_sessions = QListWidget()
        self.list_sessions.setObjectName("SessionList")
        self.list_sessions.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.list_sessions, stretch=1)

        self.lbl_llm_status = QLabel()
        self.lbl_llm_status.setObjectName("SubtitleLabel")
        self._refresh_llm_status_label()
        layout.addWidget(self.lbl_llm_status)

        dock.setWidget(container)
        return dock

    def _build_center_panel(self) -> QWidget:
        container = QWidget()
        container.setObjectName("CenterPanel")

        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Top bar and status area remain at the top
        root_layout.addWidget(self._build_top_bar())
        root_layout.addWidget(self._build_status_area())

        # Use a vertical splitter so the chat area occupies the top region
        # and utility tabs (Files / Agent Logs / Apply Code) live below it.
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        chat_widget = self._build_chat_area()
        splitter.addWidget(chat_widget)

        # Utility tabs are now embedded inside the center panel (bottom of splitter)
        tabs = QTabWidget()
        tabs.setObjectName("UtilityTabs")
        tabs.addTab(self._build_files_tab(), "Files")
        tabs.addTab(self._build_agent_logs_tab(), "Agent Logs")
        tabs.addTab(self._build_apply_code_tab(), "Apply Code")
        splitter.addWidget(tabs)

        # Make chat area take more space by default
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter, stretch=1)
        root_layout.addLayout(self._build_composer_row())

        return container

    def _build_top_bar(self) -> QWidget:
        top_bar = QWidget()
        top_bar.setObjectName("TopBar")
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        self.btn_select_folder = QPushButton("Select Project")
        self.btn_select_folder.setObjectName("IconButton")
        layout.addWidget(self.btn_select_folder)

        self.btn_scan = QPushButton("Scan Project")
        self.btn_scan.setObjectName("PrimaryButton")
        self.btn_scan.setEnabled(False)
        self.btn_scan.setToolTip("Select a project folder first.")
        layout.addWidget(self.btn_scan)

        self.lbl_project_name = QLabel("No project selected")
        self.lbl_project_name.setObjectName("TitleLabel")
        self.lbl_project_name.setWordWrap(True)
        layout.addWidget(self.lbl_project_name, stretch=1)

        self.btn_load_blueprint = QPushButton("📋 Load Blueprint")
        self.btn_load_blueprint.setObjectName("IconButton")
        self.btn_load_blueprint.setToolTip("Blueprint file load karo (any format)")
        layout.addWidget(self.btn_load_blueprint)

        self.btn_progress = QPushButton("📊 Progress")
        self.btn_progress.setObjectName("IconButton")
        self.btn_progress.setToolTip("Current blueprint progress dekho")
        self.btn_progress.setEnabled(False)
        layout.addWidget(self.btn_progress)

        return top_bar

    def _build_status_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_progress_detail = QLabel("")
        self.lbl_progress_detail.setObjectName("SubtitleLabel")
        self.lbl_progress_detail.setVisible(False)
        layout.addWidget(self.lbl_progress_detail)

        return container

    def _build_chat_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Session Row: [Session Title] [Model Status] [Text size A- A+]
        session_row = QHBoxLayout()
        session_row.setSpacing(8)

        self.lbl_active_session = QLabel("hello kaise ho")
        self.lbl_active_session.setObjectName("TitleLabel")
        self.lbl_active_session.setWordWrap(False)
        session_row.addWidget(self.lbl_active_session)

        session_row.addStretch(1)

        self.lbl_model_status = QLabel("Model: Auto (Groq → OpenRouter)")
        self.lbl_model_status.setObjectName("SubtitleLabel")
        session_row.addWidget(self.lbl_model_status)

        zoom_label = QLabel("Text size")
        zoom_label.setObjectName("SubtitleLabel")
        session_row.addWidget(zoom_label)

        self.btn_font_decrease = QPushButton("A-")
        self.btn_font_decrease.setObjectName("IconButton")
        self.btn_font_decrease.setFixedWidth(32)
        session_row.addWidget(self.btn_font_decrease)

        self.btn_font_increase = QPushButton("A+")
        self.btn_font_increase.setObjectName("IconButton")
        self.btn_font_increase.setFixedWidth(32)
        session_row.addWidget(self.btn_font_increase)

        layout.addLayout(session_row)

        # 🆕 ChromaDB / Semantic Search Status Indicator
        self.lbl_search_mode = QLabel("")
        self.lbl_search_mode.setObjectName("SubtitleLabel")
        self._check_semantic_search_status()
        session_row.addWidget(self.lbl_search_mode)

        # Chat log - zyada height milega ab
        self.txt_chat_log = QTextBrowser()
        self.txt_chat_log.setObjectName("ChatLog")
        self.txt_chat_log.setOpenExternalLinks(False)
        self.txt_chat_log.setPlaceholderText("Scan summary and AI responses will appear here.")
        layout.addWidget(self.txt_chat_log, stretch=1)

        return container

    def _build_composer_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self.btn_attach_file = QPushButton("📎")
        self.btn_attach_file.setObjectName("IconButton")
        self.btn_attach_file.setFixedWidth(38)
        self.btn_attach_file.setToolTip("Attach a file path into your question")
        row.addWidget(self.btn_attach_file)

        self.txt_query_input = QLineEdit()
        self.txt_query_input.setObjectName("ComposerInput")
        self.txt_query_input.setPlaceholderText(
            "Ask about this codebase, paste analyzer JSON payload, or type a task..."
        )
        self.txt_query_input.setClearButtonEnabled(True)
        row.addWidget(self.txt_query_input, stretch=1)

        self.btn_send_query = QPushButton("Send")
        self.btn_send_query.setObjectName("PrimaryButton")
        self.btn_send_query.setMinimumWidth(88)
        row.addWidget(self.btn_send_query)

        # --- Agent control buttons moved next to Send button (single-window mode) ---
        self.btn_start_agent = QPushButton("▶ Start Agent")
        self.btn_start_agent.setToolTip("Chat box ke text ko instruction maan kar agent start karega")
        self.btn_start_agent.setEnabled(_OPENHANDS_AVAILABLE)
        self.btn_start_agent.setStyleSheet(\"\"\"
            QPushButton { 
                background-color: #4f7cff; color: white; font-weight: bold; 
                border: none; padding: 6px 12px; border-radius: 4px; 
            }
            QPushButton:disabled { background-color: #2A2A38; color: #666666; }
            QPushButton:hover:!disabled { background-color: #658cff; }
        \"\"\")
        row.addWidget(self.btn_start_agent)

        self.btn_approve_agent = QPushButton("✅ Approve")
        self.btn_approve_agent.setEnabled(False)
        self.btn_approve_agent.setStyleSheet(\"\"\"
            QPushButton { 
                background-color: #2E7D32; color: white; font-weight: bold; 
                border: none; padding: 6px 12px; border-radius: 4px; 
            }
            QPushButton:disabled { background-color: #2A2A38; color: #666666; }
            QPushButton:hover:!disabled { background-color: #388E3C; }
        \"\"\")
        row.addWidget(self.btn_approve_agent)

        self.btn_reject_agent = QPushButton("❌ Reject")
        self.btn_reject_agent.setEnabled(False)
        self.btn_reject_agent.setStyleSheet(\"\"\"
            QPushButton { 
                background-color: #C62828; color: white; font-weight: bold; 
                border: none; padding: 6px 12px; border-radius: 4px; 
            }
            QPushButton:disabled { background-color: #2A2A38; color: #666666; }
            QPushButton:hover:!disabled { background-color: #D32F2F; }
        \"\"\")
        row.addWidget(self.btn_reject_agent)

        self.btn_kill_agent = QPushButton("⏹ Kill")
        self.btn_kill_agent.setEnabled(False)
        self.btn_kill_agent.setStyleSheet(\"\"\"
            QPushButton { 
                background-color: #E65100; color: white; font-weight: bold; 
                border: none; padding: 6px 12px; border-radius: 4px; 
            }
            QPushButton:disabled { background-color: #2A2A38; color: #666666; }
            QPushButton:hover:!disabled { background-color: #F57C00; }
        \"\"\")
        row.addWidget(self.btn_kill_agent)

        return row

    def _build_utility_dock(self) -> QDockWidget:
        dock = QDockWidget("Workspace", self)
        dock.setObjectName("UtilityDock")
        dock.setMinimumWidth(280)

        tabs = QTabWidget()
        tabs.setObjectName("UtilityTabs")
        tabs.addTab(self._build_files_tab(), "Files")
        tabs.addTab(self._build_agent_logs_tab(), "Agent Logs")
        tabs.addTab(self._build_apply_code_tab(), "Apply Code")

        dock.setWidget(tabs)
        return dock

    def _build_apply_code_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hint = QLabel(
            "Claude se mila hua structured code-block yahan paste karo aur "
            "'Apply' dabao. Koi AI/API call nahi hoti — seedha file likhi jaati hai.\n\n"
            "Format:\n"
            "### FILE: path/to/file.py\n"
            "### ACTION: replace (ya create)\n"
            "<<<CODE_START>>>\n"
            "...code...\n"
            "<<<CODE_END>>>"
        )
        hint.setObjectName("SubtitleLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.txt_apply_code_input = QTextEdit()
        self.txt_apply_code_input.setObjectName("AgentLogs")
        self.txt_apply_code_input.setPlaceholderText(
            "### FILE: ui/example.py\n### ACTION: replace\n<<<CODE_START>>>\n...\n<<<CODE_END>>>"
        )
        layout.addWidget(self.txt_apply_code_input, stretch=1)

        self.btn_apply_code = QPushButton("📥 Apply Code Block(s)")
        self.btn_apply_code.setObjectName("PrimaryButton")
        layout.addWidget(self.btn_apply_code)

        self.txt_apply_code_results = QTextEdit()
        self.txt_apply_code_results.setObjectName("AgentLogs")
        self.txt_apply_code_results.setReadOnly(True)
        self.txt_apply_code_results.setMaximumHeight(140)
        self.txt_apply_code_results.setPlaceholderText("Apply results yahan dikhenge...")
        layout.addWidget(self.txt_apply_code_results)

        return container

    def _build_files_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.lbl_files_hint = QLabel("Select a project folder to see its file tree.")
        self.lbl_files_hint.setObjectName("SubtitleLabel")
        self.lbl_files_hint.setWordWrap(True)
        layout.addWidget(self.lbl_files_hint)

        self.tree_files = QTreeWidget()
        self.tree_files.setObjectName("FileTree")
        self.tree_files.setHeaderHidden(True)
        layout.addWidget(self.tree_files, stretch=1)

        return container

    def _build_agent_logs_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Status line (keeps visible in Agent Logs tab)
        self.lbl_agent_status = QLabel("⚪ Agent Idle")
        self.lbl_agent_status.setStyleSheet(
            "color: #9aa1b5; font-size: 13px; font-weight: bold; padding: 4px 0;"
        )
        layout.addWidget(self.lbl_agent_status)

        # Agent Logs Text Area (read-only)
        self.txt_agent_logs = QTextEdit()
        self.txt_agent_logs.setObjectName("AgentLogs")
        self.txt_agent_logs.setReadOnly(True)
        self.txt_agent_logs.setStyleSheet(
            "QTextEdit { background-color: #1E1E28; color: #E8E8ED; "
            "font-family: Consolas, 'Courier New', monospace; "
            "font-size: 14px; font-weight: 600; }"
        )

        if _OPENHANDS_AVAILABLE:
            self.txt_agent_logs.setPlainText(
                "OpenHands Agent Ready.\n"
                "1. Chat box mein apna task likhein "
                "(e.g., 'Create a file named test.txt').\n"
                "2. 'Start Agent' button dabayein.\n"
                "3. Jab agent permission maange, toh Approve ya Reject karein."
            )
        else:
            self.txt_agent_logs.setPlainText(
                "⚠️ OpenHands SDK is not installed in the current Python environment.\n"
                "Agent features are disabled."
            )

        layout.addWidget(self.txt_agent_logs, stretch=1)
        return container

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.btn_select_folder.clicked.connect(self._on_select_folder_clicked)
        self.btn_scan.clicked.connect(self._on_scan_clicked)
        self.btn_send_query.clicked.connect(self._on_send_or_stop_clicked)
        self.btn_attach_file.clicked.connect(self._on_attach_file_clicked)
        self.btn_font_increase.clicked.connect(self._on_increase_font_size)
        self.btn_font_decrease.clicked.connect(self._on_decrease_font_size)
        self.btn_new_chat.clicked.connect(self._on_new_chat_clicked)
        self.btn_start_agent.clicked.connect(self._on_start_agent_clicked)
        self.btn_approve_agent.clicked.connect(self._on_approve_agent_clicked)
        self.btn_reject_agent.clicked.connect(self._on_reject_agent_clicked)
        self.btn_kill_agent.clicked.connect(self._on_kill_agent_clicked)
        self.btn_load_blueprint.clicked.connect(self._on_load_blueprint_clicked)
        self.btn_progress.clicked.connect(self._on_progress_clicked)
        self.btn_apply_code.clicked.connect(self._on_apply_code_clicked)
        

        self.txt_query_input.returnPressed.connect(self._on_send_or_stop_clicked)
        self.txt_session_search.textChanged.connect(self._on_session_search_changed)

        self.list_sessions.itemClicked.connect(self._on_session_item_clicked)
        self.list_sessions.customContextMenuRequested.connect(self._on_session_context_menu)
        self.txt_chat_log.setOpenLinks(False)
        self.txt_chat_log.anchorClicked.connect(self._on_copy_link_clicked)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _on_toggle_theme(self, checked: bool) -> None:
        self._theme = "dark" if checked else "light"
        self._apply_theme()

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(DARK_QSS if self._theme == "dark" else LIGHT_QSS)

        chat_bg = get_chat_area_background(self._theme)
        self.txt_chat_log.setStyleSheet(
            f"QTextEdit#ChatLog {{ background-color: {chat_bg}; border: none; }}"
        )
        self._rerender_chat_log()

    # ------------------------------------------------------------------
    # Chat rendering / zoom
    # ------------------------------------------------------------------

    def _append_message(self, role: str, text: str, persist: bool = True) -> None:
        copy_id = len(self._display_messages)
        self._display_messages.append((role, text))
        self.txt_chat_log.append(
            format_message_html(
                role,
                text,
                font_size_pt=self._chat_font_size,
                theme=self._theme,
                copy_id=copy_id,
            )
        )

        if persist and self._active_session_id and role in ("user", "assistant", "system"):
            self.storage.add_message(self._active_session_id, role, text)

            if role == "user":
                self._maybe_auto_title_session(text)

    def _rerender_chat_log(self) -> None:
        self.txt_chat_log.clear()
        for index, (role, text) in enumerate(self._display_messages):
            self.txt_chat_log.append(
                format_message_html(
                    role,
                    text,
                    font_size_pt=self._chat_font_size,
                    theme=self._theme,
                    copy_id=index,
                )
            )

    def _on_increase_font_size(self) -> None:
        if self._chat_font_size < MAX_FONT_SIZE_PT:
            self._chat_font_size += 1
            self._rerender_chat_log()

    def _on_decrease_font_size(self) -> None:
        if self._chat_font_size > MIN_FONT_SIZE_PT:
            self._chat_font_size -= 1
            self._rerender_chat_log()

    def _on_copy_link_clicked(self, url) -> None:
        """Message ke neeche 📋 Copy link click → clipboard mein copy."""
        href = url.toString()
        if not href.startswith("copy:"):
            return
        try:
            index = int(href.split(":")[1])
        except (ValueError, IndexError):
            return
        if index < len(self._display_messages):
            _role, text = self._display_messages[index]
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage("📋 Message copied to clipboard", 3000)

    # ------------------------------------------------------------------
    # Session sidebar
    # ------------------------------------------------------------------

    def _refresh_llm_status_label(self) -> None:
        has_groq_key = bool(os.getenv("GROQ_API_KEY"))
        has_openrouter_key = bool(os.getenv("OPENROUTER_API_KEY"))

        if has_groq_key:
            self.lbl_llm_status.setText("🟢 Groq key configured")
        elif has_openrouter_key:
            self.lbl_llm_status.setText("🟡 OpenRouter key configured")
        else:
            self.lbl_llm_status.setText("🔴 No LLM API key found in .env")

    def _on_session_search_changed(self, _text: str) -> None:
        self._reload_sessions_list(select_session_id=self._active_session_id)

    def _reload_sessions_list(self, select_session_id: str | None = None) -> None:
        self.list_sessions.blockSignals(True)
        self.list_sessions.clear()

        search_text = self.txt_session_search.text().strip().lower()
        sessions = self.storage.list_sessions()

        if search_text:
            sessions = [
                session
                for session in sessions
                if search_text in (session.get("title") or "").lower()
            ]

        pinned = [session for session in sessions if session.get("pinned")]
        others = [session for session in sessions if not session.get("pinned")]

        if pinned:
            self._add_group_header("📌 Pinned")
            for session in pinned:
                self._add_session_item(session)

        groups: dict[str, list[dict]] = {
            "Today": [],
            "Yesterday": [],
            "Previous 7 Days": [],
            "Older": [],
        }

        today = date.today()
        for session in others:
            updated_date = self._parse_date_safe(session.get("updated_at"), today)
            delta_days = (today - updated_date).days

            if delta_days <= 0:
                groups["Today"].append(session)
            elif delta_days == 1:
                groups["Yesterday"].append(session)
            elif delta_days <= 7:
                groups["Previous 7 Days"].append(session)
            else:
                groups["Older"].append(session)

        for label in ("Today", "Yesterday", "Previous 7 Days", "Older"):
            if groups[label]:
                self._add_group_header(label)
                for session in groups[label]:
                    self._add_session_item(session)

        self.list_sessions.blockSignals(False)

        target_id = select_session_id or self._active_session_id
        if target_id:
            self._select_session_in_list(target_id)

    @staticmethod
    def _parse_date_safe(iso_string: str | None, fallback: date) -> date:
        if not iso_string:
            return fallback
        try:
            return datetime.fromisoformat(iso_string).date()
        except ValueError:
            return fallback

    def _add_group_header(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)

        font = QFont()
        font.setBold(True)
        item.setFont(font)
        item.setForeground(QBrush(QColor("#8f96ab")))

        self.list_sessions.addItem(item)

    def _add_session_item(self, session: dict) -> None:
        title = session.get("title") or "New Chat"
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, session)
        item.setToolTip(title)
        self.list_sessions.addItem(item)

    def _select_session_in_list(self, session_id: str) -> None:
        for row in range(self.list_sessions.count()):
            item = self.list_sessions.item(row)
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and data.get("session_id") == session_id:
                self.list_sessions.setCurrentItem(item)
                return

    def _load_initial_session(self) -> None:
        sessions = self.storage.list_sessions()

        if not sessions:
            session_id = self.storage.create_session("New Chat")
        else:
            session_id = sessions[0]["session_id"]

        self._reload_sessions_list(select_session_id=session_id)
        self._switch_to_session(session_id)

    def _switch_to_session(self, session_id: str) -> None:
        self._active_session_id = session_id

        session_rows = [
            session
            for session in self.storage.list_sessions()
            if session["session_id"] == session_id
        ]
        session_title = session_rows[0]["title"] if session_rows else "New Chat"
        self.lbl_active_session.setText(session_title)

        self._display_messages.clear()
        self.txt_chat_log.clear()
        self._chat_history.clear()

        for message in self.storage.get_messages(session_id):
            sender = message["sender"]
            content = message["content"]

            self._append_message(sender, content, persist=False)

            if sender in ("user", "assistant"):
                self._chat_history.append({"role": sender, "content": content})

        self._chat_history = self._chat_history[-MAX_HISTORY_MESSAGES:]

    def _on_session_item_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return

        session_id = data["session_id"]
        if session_id != self._active_session_id:
            self._switch_to_session(session_id)

    def _on_new_chat_clicked(self) -> None:
        session_id = self.storage.create_session("New Chat")
        self._reload_sessions_list(select_session_id=session_id)
        self._switch_to_session(session_id)
        self.txt_query_input.setFocus()

    def _on_session_context_menu(self, position) -> None:
        item = self.list_sessions.itemAt(position)
        if item is None:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return

        menu = QMenu(self)
        action_rename = menu.addAction("Rename")
        action_pin = menu.addAction("Unpin" if data.get("pinned") else "Pin")
        action_export = menu.addAction("Export chat...")
        menu.addSeparator()
        action_delete = menu.addAction("Delete")

        chosen = menu.exec(self.list_sessions.mapToGlobal(position))

        if chosen == action_rename:
            self._handle_rename_session(data)
        elif chosen == action_pin:
            self._handle_toggle_pin(data)
        elif chosen == action_export:
            self._handle_export_session(data)
        elif chosen == action_delete:
            self._handle_delete_session(data)

    def _handle_rename_session(self, session: dict) -> None:
        new_title, ok = QInputDialog.getText(
            self,
            "Rename Chat",
            "New title:",
            text=session.get("title", ""),
        )

        if ok and new_title.strip():
            self.storage.rename_session(session["session_id"], new_title.strip())
            self._reload_sessions_list(select_session_id=self._active_session_id)

            if session["session_id"] == self._active_session_id:
                self.lbl_active_session.setText(new_title.strip())

    def _handle_toggle_pin(self, session: dict) -> None:
        self.storage.set_pinned(session["session_id"], not session.get("pinned"))
        self._reload_sessions_list(select_session_id=self._active_session_id)

    def _handle_export_session(self, session: dict) -> None:
        default_name = f"{session.get('title', 'chat')}.md"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Chat",
            default_name,
            "Markdown Files (*.md);;Text Files (*.txt)",
        )

        if not path:
            return

        messages = self.storage.get_messages(session["session_id"])
        lines = [f"# {session.get('title', 'Chat')}\n"]

        for message in messages:
            label = "**You**" if message["sender"] == "user" else f"**{message['sender'].title()}**"
            lines.append(f"{label} ({message['timestamp']}):\n{message['content']}\n")

        try:
            with open(path, "w", encoding="utf-8") as file_handle:
                file_handle.write("\n---\n".join(lines))
            self.statusBar().showMessage(f"Exported to {path}", 5000)
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def _handle_delete_session(self, session: dict) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete Chat",
            f"Delete \"{session.get('title', 'this chat')}\"? This cannot be undone.",
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.storage.delete_session(session["session_id"])

        if session["session_id"] == self._active_session_id:
            remaining = self.storage.list_sessions()

            if remaining:
                next_id = remaining[0]["session_id"]
            else:
                next_id = self.storage.create_session("New Chat")

            self._reload_sessions_list(select_session_id=next_id)
            self._switch_to_session(next_id)
        else:
            self._reload_sessions_list(select_session_id=self._active_session_id)

    def _maybe_auto_title_session(self, first_user_message: str) -> None:
        sessions = [
            session
            for session in self.storage.list_sessions()
            if session["session_id"] == self._active_session_id
        ]

        if not sessions:
            return

        current_title = sessions[0].get("title") or "New Chat"
        if current_title != "New Chat":
            return

        self.storage.auto_title_from_first_message(self._active_session_id, first_user_message)
        self._reload_sessions_list(select_session_id=self._active_session_id)

        refreshed = [
            session
            for session in self.storage.list_sessions()
            if session["session_id"] == self._active_session_id
        ]

        if refreshed:
            self.lbl_active_session.setText(refreshed[0]["title"])

    # ------------------------------------------------------------------
    # Project selection / file tree
    # ------------------------------------------------------------------

    def _on_select_folder_clicked(self) -> None:
        chosen_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Project Folder",
            os.path.expanduser("~"),
        )
        if not chosen_dir:
            return

        self._project_root = chosen_dir
        self.lbl_project_name.setText(os.path.basename(chosen_dir) or chosen_dir)
        self.lbl_project_name.setToolTip(chosen_dir)
        self._populate_file_tree(chosen_dir)
        self._refresh_action_states()

        # Folder save karo taaki agli baar auto-load ho
        settings = QSettings("ERP-AI-Tool", "Medical")
        settings.setValue("last_project_folder", chosen_dir)

        self.statusBar().showMessage(f"Project selected: {chosen_dir}", 5000)

    def _populate_file_tree(self, root_path: str) -> None:
        self.tree_files.clear()
        self.lbl_files_hint.setText(root_path)

        root_item = QTreeWidgetItem([os.path.basename(root_path) or root_path])
        self.tree_files.addTopLevelItem(root_item)
        self._add_tree_children(root_item, root_path)
        root_item.setExpanded(True)

    def _add_tree_children(self, parent_item: QTreeWidgetItem, folder_path: str) -> None:
        try:
            entries = sorted(
                os.listdir(folder_path),
                key=lambda name: (
                    not os.path.isdir(os.path.join(folder_path, name)),
                    name.lower(),
                ),
            )
        except OSError:
            return

        for name in entries:
            if name in TREE_IGNORE_DIRS or name.startswith("."):
                continue

            full_path = os.path.join(folder_path, name)
            child_item = QTreeWidgetItem([name])
            parent_item.addChild(child_item)

            if os.path.isdir(full_path):
                self._add_tree_children(child_item, full_path)

    # ------------------------------------------------------------------
    # UI state
    # ------------------------------------------------------------------

    def _refresh_action_states(self) -> None:
        has_project = bool(self._project_root)

        is_scanning = self._scan_worker is not None and self._scan_worker.isRunning()
        is_querying = self._query_worker is not None and self._query_worker.isRunning()
        is_busy = is_scanning or is_querying

        self.btn_scan.setEnabled(has_project and not is_busy)
        self.btn_scan.setToolTip("" if has_project else "Select a project folder first.")

        self.btn_select_folder.setEnabled(not is_busy)
        self.txt_query_input.setEnabled(not is_busy)
        self.btn_attach_file.setEnabled(not is_busy)
        self.btn_new_chat.setEnabled(not is_busy)
        self.list_sessions.setEnabled(not is_busy)

        # Send/Stop button querying के दौरान Stop के लिए enabled रहता है।
        self.btn_send_query.setEnabled(not is_scanning)

    def _set_scanning_ui_state(self, active: bool) -> None:
        self.progress_bar.setVisible(active)
        self.lbl_progress_detail.setVisible(active)
        self.lbl_progress_detail.setText("Scanning project..." if active else "")
        self._refresh_action_states()

    def _set_querying_ui_state(self, active: bool) -> None:
        self.progress_bar.setVisible(active)
        self.lbl_progress_detail.setVisible(active)
        self.lbl_progress_detail.setText("Thinking..." if active else "")
        self.btn_send_query.setText("Stop" if active else "Send")
        self._refresh_action_states()

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _on_scan_clicked(self) -> None:
        if not self._project_root:
            return

        self._set_scanning_ui_state(active=True)
        self._append_message("system", f"Scanning project: `{self._project_root}`")

        self._scan_worker = ScanWorker(self._project_root, parent=self)
        self._scan_worker.finished_ok.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.finished.connect(self._on_scan_thread_finished)
        self._scan_worker.start()

    def _on_scan_finished(self, result: dict) -> None:
        added = result.get("added_count", 0)
        updated = result.get("updated_count", 0)
        removed = result.get("removed_count", 0)
        total = result.get("total_files", 0)

        summary = (
            "**Scan complete.**\n\n"
            f"- Added: {added}\n"
            f"- Updated: {updated}\n"
            f"- Removed: {removed}\n"
            f"- Total files indexed: {total}"
        )

        self._append_message("system", summary)

        if self._project_root:
            self._populate_file_tree(self._project_root)

        self.statusBar().showMessage("Scan complete.", 5000)
        logger.info(
            "Project scan finished: added=%s updated=%s removed=%s total=%s",
            added,
            updated,
            removed,
            total,
        )

    def _on_scan_failed(self, error_message: str) -> None:
        self._append_message("error", error_message)
        self.statusBar().showMessage("Scan failed.", 5000)
        QMessageBox.critical(self, "Scan Failed", error_message)

    def _on_scan_thread_finished(self) -> None:
        self._set_scanning_ui_state(active=False)
        self._scan_worker = None

    # ------------------------------------------------------------------
    # Query / stop
    # ------------------------------------------------------------------

    def _on_send_or_stop_clicked(self) -> None:
        if self._query_worker is not None and self._query_worker.isRunning():
            self._on_stop_query_clicked()
        else:
            self._on_send_query_clicked()

    def _on_send_query_clicked(self) -> None:
        if self._query_worker is not None and self._query_worker.isRunning():
            return

        query_text = self.txt_query_input.text().strip()
        if not query_text:
            return

        if not self._active_session_id:
            self._active_session_id = self.storage.create_session("New Chat")
            self._reload_sessions_list(select_session_id=self._active_session_id)

        self._append_message("user", query_text)
        self.txt_query_input.clear()

        if self._try_route_tool(query_text):
            return

        self._last_query_text = query_text
        self._set_querying_ui_state(active=True)

        self._query_worker = QueryWorker(
            query_text,
            history=list(self._chat_history),
            parent=self,
        )
        self._query_worker.finished_ok.connect(self._on_query_finished)
        self._query_worker.failed.connect(self._on_query_failed)
        self._query_worker.finished.connect(self._on_query_thread_finished)
        self._query_worker.start()

    def _on_stop_query_clicked(self) -> None:
        """
        Temporary stop mechanism.
        Future में इसे cancellable worker/subprocess से replace करना चाहिए।
        """
        if self._query_worker is None or not self._query_worker.isRunning():
            return

        self._stop_requested = True
        self._query_worker.terminate()
        self._query_worker.wait(1500)

        self._append_message("system", "Query stopped by user. Response may be incomplete.")
        self._set_querying_ui_state(active=False)
        self._query_worker = None

    def _on_query_finished(self, answer: str) -> None:
        if self._stop_requested:
            self._stop_requested = False
            return

        self._append_message("assistant", answer)
        self.statusBar().showMessage("Response received.", 5000)

        self._chat_history.append({"role": "user", "content": self._last_query_text})
        self._chat_history.append({"role": "assistant", "content": answer})
        self._chat_history = self._chat_history[-MAX_HISTORY_MESSAGES:]

    def _on_query_failed(self, error_message: str) -> None:
        self._append_message("error", error_message)
        self.statusBar().showMessage("Query failed.", 5000)

    def _on_query_thread_finished(self) -> None:
        self._set_querying_ui_state(active=False)
        self._query_worker = None

    # ------------------------------------------------------------------
    # Attachment
    # ------------------------------------------------------------------

    def _on_attach_file_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Attach File")
        if not path:
            return

        current_text = self.txt_query_input.text()
        prefix = f"[Referring to file: {path}] "
        self.txt_query_input.setText(prefix + current_text)
        self.txt_query_input.setFocus()
        self.txt_query_input.setCursorPosition(len(self.txt_query_input.text()))

    # ------------------------------------------------------------------
    # Tool routing for analyzer JSON payloads
    # ------------------------------------------------------------------

    def _try_route_tool(self, query_text: str) -> bool:
        text = query_text.strip()

        if not (text.startswith("{") and text.endswith("}")):
            return False

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return False

        if not isinstance(payload, dict):
            return False

        try:
            if "pr_id" in payload and "items" in payload:
                result = analyze_purchase_requisition(payload)
                self._append_message("assistant", self._format_pr_result(result))
                return True

            if "warehouse_id" in payload and "inventory" in payload:
                result = analyze_warehouse_risk(payload)
                self._append_message("assistant", self._format_warehouse_risk_result(result))
                return True

            if "company_code" in payload and "transactions" in payload:
                result = run_audit(payload)
                self._append_message("assistant", self._format_audit_result(result))
                return True

            if "factory_id" in payload and "work_orders" in payload:
                result = schedule_jobs(payload)
                self._append_message("assistant", self._format_production_result(result))
                return True

            if "fulfillment_center_id" in payload and "warehouses" in payload:
                result = evaluate_inventory_allocation(payload)
                self._append_message("assistant", self._format_inventory_allocation_result(result))
                return True

        except Exception as exc:  # noqa: BLE001
            self._append_message("error", f"Tool execution failed: {exc}")
            return True

        return False

    def _format_pr_result(self, result: dict) -> str:
        return (
            "**Purchase Requisition Analysis**\n\n"
            f"- PR ID: `{result['pr_id']}`\n"
            f"- Total Budget: ₹{result['total_budget']:,.0f}\n"
            f"- Urgency: {result['urgency']}\n"
            f"- Management Approval: {'Required' if result['requires_management_approval'] else 'Not required'}\n\n"
            f"**Summary:** {result['finance_summary']}"
        )

    def _format_warehouse_risk_result(self, result: dict) -> str:
        lines = []

        for recommendation in result.get("reorder_recommendations", []):
            lines.append(
                f"- `{recommendation['item_code']}`: usable stock "
                f"{recommendation['usable_stock']}, suggested reorder "
                f"{recommendation['suggested_reorder_qty']}"
            )

        reorder_block = "\n".join(lines) if lines else "- No reorder recommendations"

        return (
            "**Warehouse Inventory Risk Assessment**\n\n"
            f"- Warehouse: `{result['warehouse_id']}`\n"
            f"- Total at-risk value: ₹{result['total_at_risk_value']:,.2f}\n"
            f"- Critical items: {result['critical_items_count']}\n\n"
            f"**Reorder Recommendations:**\n{reorder_block}\n\n"
            f"**Summary:** {result['action_summary']}"
        )

    def _format_audit_result(self, result: dict) -> str:
        lines = []

        for txn in result.get("flagged_transactions", []):
            flags = ", ".join(txn.get("flags", []))
            lines.append(
                f"- `{txn['txn_id']}` | ₹{txn['amount']:,.2f} | "
                f"risk score {txn['risk_score']} | flags: {flags}"
            )

        flagged_block = "\n".join(lines) if lines else "- No suspicious transactions found"

        return (
            "**Financial Ledger Audit Report**\n\n"
            f"- Company: `{result['company_code']}`\n"
            f"- Transactions audited: {result['total_transactions_audited']}\n"
            f"- Suspicious transactions: {result['suspicious_transactions_count']}\n"
            f"- Total flagged amount: ₹{result['total_flagged_amount']:,.2f}\n\n"
            f"**Flagged Transactions:**\n{flagged_block}\n\n"
            f"**Summary:** {result['audit_summary']}"
        )

    def _format_production_result(self, result: dict) -> str:
        lines = []

        for detail in result.get("schedule_details", []):
            lines.append(
                f"- `{detail['order_id']}` | status: {detail['status']} | "
                f"completion: {detail['estimated_completion']} | "
                f"bottleneck: `{detail['bottleneck_center']}`"
            )

        schedule_block = "\n".join(lines) if lines else "- No scheduled orders"

        return (
            "**Production Job Scheduler Report**\n\n"
            f"- Factory: `{result['factory_id']}`\n"
            f"- Orders scheduled: {result['total_orders_scheduled']}\n"
            f"- Delayed-risk orders: {result['delayed_orders_count']}\n\n"
            f"**Schedule Details:**\n{schedule_block}\n\n"
            f"**Summary:** {result['production_summary']}"
        )

    def _format_inventory_allocation_result(self, result: dict) -> str:
        lines = []

        for warehouse in result.get("warehouse_analysis", []):
            line = (
                f"- `{warehouse['wh_id']}` | DOI: {warehouse['doi']} | "
                f"ROP: {warehouse['reorder_point']} | status: {warehouse['status']}"
            )

            if warehouse.get("action_recommended"):
                action = (
                    f" | action: {warehouse['action_recommended']} "
                    f"{warehouse.get('suggested_units') or 0} units"
                )

                if warehouse.get("source_wh"):
                    action += f" from `{warehouse['source_wh']}`"

                line += action

            lines.append(line)

        analysis_block = "\n".join(lines) if lines else "- No warehouse analysis available"

        return (
            "**Inventory Allocation Report**\n\n"
            f"- Fulfillment center: `{result['fulfillment_center_id']}`\n"
            f"- Warehouses audited: {result['total_warehouses_audited']}\n"
            f"- At-risk warehouses: {result['at_risk_warehouses_count']}\n\n"
            f"**Warehouse Analysis:**\n{analysis_block}\n\n"
            f"**Summary:** {result['rebalance_summary']}"
        )

    def _load_last_project_folder(self) -> None:
        """App start hote hi purana folder automatically load karta hai."""
        settings = QSettings("ERP-AI-Tool", "Medical")
        last_path = settings.value("last_project_folder", None)
        if last_path and os.path.isdir(last_path):
            self._project_root = last_path
            self.lbl_project_name.setText(os.path.basename(last_path) or last_path)
            self.lbl_project_name.setToolTip(last_path)
            self._populate_file_tree(last_path)
            self._refresh_action_states()

    def _auto_load_blueprint(self) -> None:
        """App start hote hi active_blueprint.json auto-detect karo."""
        try:
            from storage.blueprint_storage import get_active_blueprint
            bp = get_active_blueprint()
            if bp:
                self.btn_progress.setEnabled(True)
                title = bp.get("title", "Unknown")
                tasks_count = len(bp.get("tasks", []))
                self.statusBar().showMessage(
                    f"📋 Blueprint auto-loaded: {title} ({tasks_count} tasks)", 5000
                )
        except Exception:
            pass
            
    def _update_statusbar_datetime(self) -> None:
        """Status bar mein live date + time update karo."""
        now = datetime.now()
        self.lbl_datetime.setText(now.strftime("📅 %Y-%m-%d | ⏰ %H:%M:%S"))

  
    def eventFilter(self, obj, event) -> bool:
        """Chat window mein file drop handle karo."""
        # Use QEvent.Type enum comparisons and event.type() — more robust than using event.Type
        if obj == self.txt_chat_log:
            try:
                et = event.type()
                if et == QEvent.Type.DragEnter:
                    if event.mimeData().hasUrls():
                        event.acceptProposedAction()
                        return True
                elif et == QEvent.Type.Drop:
                    urls = event.mimeData().urls()
                    if urls:
                        file_path = urls[0].toLocalFile()
                        self._handle_blueprint_drop(file_path)
                        return True
            except Exception:
                # Defensive: if something unexpected about the event object happens, fall-through to default
                return super().eventFilter(obj, event)
        return super().eventFilter(obj, event)

    def _handle_blueprint_drop(self, file_path: str) -> None:
        """Dropped file ko blueprint ke roop mein parse karke load karo."""
        try:
            self._append_message("system", f"📄 Blueprint parse ho raha hai: `{os.path.basename(file_path)}`")

            from storage.blueprint_parser import parse_blueprint_file
            blueprint_data = parse_blueprint_file(file_path)

            from storage.blueprint_storage import load_blueprint
            load_blueprint(blueprint_data)

            self.btn_progress.setEnabled(True)
            title = blueprint_data.get("title", "Unknown")
            tasks_count = len(blueprint_data.get("tasks", []))
            self._append_message(
                "system",
                f"✅ **Blueprint loaded via Drag & Drop!**\n"
                f"**Title:** {title}\n"
                f"**Tasks:** {tasks_count}"
            )
        except Exception as exc:
            self._append_message("error", f"❌ Blueprint load failed: {exc}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        # Scan/Query workers cleanup
        for worker in (self._scan_worker, self._query_worker):
            if worker is not None and worker.isRunning():
                worker.terminate()
                worker.wait(1000)

        # Agent worker cleanup (T36)
        if self._agent_worker is not None:
            try:
                if self._agent_worker.isRunning():
                    # Conversation pause karo gracefully
                    if self._agent_worker._conversation is not None:
                        try:
                            self._agent_worker._conversation.pause()
                        except Exception:
                            pass
                    self._agent_worker.terminate()
                    self._agent_worker.wait(2000)
            except Exception:
                pass
            finally:
                self._agent_worker = None

        event.accept()

    # ------------------------------------------------------------------ #
    # OpenHands Agent Controls
    # ------------------------------------------------------------------ #
    # Replace start of method _on_start_agent_clicked with this guarded version
    def _on_start_agent_clicked(self) -> None:
        """Agent start karo - selected project folder mein kaam karega."""
        # Guard: OpenHands not installed?
        if not _OPENHANDS_AVAILABLE:
            QMessageBox.warning(
                self,
                "Agent Not Available",
                "OpenHands SDK not installed or not available in this environment.\n"
                "Agent features are disabled. To enable, install requirements:\n"
                "pip install openhands-sdk openhands-tools\n\n"
                "Note: you may also need to add API keys to a .env file."
            )
            return

        if self._agent_worker is not None and self._agent_worker.isRunning():
            QMessageBox.warning(self, "Agent Running", "Agent pehle se chal raha hai. Wait karein ya Kill karein.")
            return
       
        instruction = self.txt_query_input.text().strip()
        if not instruction:
            QMessageBox.warning(self, "Missing Instruction", "Pehle chat box mein agent ke liye koi task likhein.")
            return

        # Hamesha selected project folder use karo
        workspace = self._project_root
        if not workspace:
            QMessageBox.warning(
                self, "No Workspace",
                "Pehle 'Select Project' se folder select karein.\n"
                "Agent usi folder mein kaam karega."
            )
            return

        # ─── Separator line: naya task shuru ───
        self.txt_agent_logs.append("\n" + "═" * 50)
        self.txt_agent_logs.append(f"🚀 NEW TASK: {instruction}")
        self.txt_agent_logs.append(f"📁 Workspace: {workspace}")
        self.txt_agent_logs.append("═" * 50)

        self._append_message("system", f"🤖 **Agent Started** in `{workspace}`\nTask: `{instruction}`")

        # Agent worker create karo
        self._agent_worker = OpenHandsWorker(
            workspace_path=workspace,
            user_instruction=instruction,
            parent=self
        )

        self._agent_worker.event_received.connect(self._on_agent_event)
        self._agent_worker.waiting_for_confirmation.connect(self._on_agent_waiting)
        self._agent_worker.finished_ok.connect(self._on_agent_finished)
        self._agent_worker.failed.connect(self._on_agent_failed)

        self.btn_start_agent.setEnabled(False)
        self.btn_kill_agent.setEnabled(True)
        self._agent_elapsed_seconds = 0
        self._agent_tick_timer.start(1000)
        self._set_agent_status("🔄 Agent Processing... (0s)", "#4f7cff")

        self._agent_worker.start()

    def _on_agent_tick(self) -> None:
        """Har second call hota hai jab tak agent processing mein hai — live
        elapsed-time indicator dikhata hai taaki user ko lage kaam chal raha hai."""
        self._agent_elapsed_seconds += 1
        dots = "." * ((self._agent_elapsed_seconds % 3) + 1)
        self.lbl_agent_status.setText(f"🔄 Agent Processing{dots} ({self._agent_elapsed_seconds}s)")

    def _on_progress_clicked(self) -> None:
        """Progress report dikhao."""
        from storage.blueprint_storage import get_progress_report, compare_with_repo

        report = get_progress_report()
        self.txt_agent_logs.append("\n" + report + "\n")

        # Agar project root select hai to repo comparison bhi karo
        if self._project_root:
            comparison = compare_with_repo(self._project_root)
            self.txt_agent_logs.append("\n" + comparison + "\n")

    def _on_apply_code_clicked(self) -> None:
        """Apply Code Block tab ka 'Apply' button — zero-LLM file writer."""
        if not self._project_root:
            QMessageBox.warning(
                self, "No Project Selected",
                "Pehle 'Select Project' se ek folder choose karo — "
                "usi folder ke andar files likhi jayengi."
            )
            return

        raw_text = self.txt_apply_code_input.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Empty Input", "Pehle code block paste karo.")
            return

        results = apply_all_blocks(self._project_root, raw_text)

        self.txt_apply_code_results.clear()
        success_count = 0
        for result in results:
            self.txt_apply_code_results.append(result.message)
            if result.backup_path:
                self.txt_apply_code_results.append(f"   (backup: {result.backup_path})")
            if result.success:
                success_count += 1

        self.statusBar().showMessage(
            f"Apply Code: {success_count}/{len(results)} file(s) updated.", 6000
        )

        if success_count > 0:
            self._append_message(
                "system",
                f"📥 **Apply Code Block:** {success_count}/{len(results)} file(s) updated "
                f"(zero API cost — direct file write)."
            )
            if self._project_root:
                self._populate_file_tree(self._project_root)

    # Chat mein user ye likh sakta hai:
    # "blueprint status" → progress report
    # "blueprint compare" → repo comparison
    # "blueprint tasks" → all tasks list

    def _handle_blueprint_command(self, text: str) -> bool:
        """Blueprint commands handle karo. Returns True if handled."""
        text_lower = text.strip().lower()

        if text_lower in ("blueprint status", "bp status", "progress"):
            from storage.blueprint_storage import get_progress_report
            report = get_progress_report()
            self._append_message("system", report)
            return True

        if text_lower in ("blueprint compare", "bp compare"):
            if self._project_root:
                from storage.blueprint_storage import compare_with_repo
                comparison = compare_with_repo(self._project_root)
                self._append_message("system", comparison)
            else:
                self._append_message("system", "Pehle project folder select karo.")
            return True

        if text_lower in ("blueprint tasks", "bp tasks"):
            from storage.blueprint_storage import get_active_blueprint
            bp = get_active_blueprint()
            if bp:
                lines = [f"📋 {bp['title']}", ""]
                for task in bp["tasks"]:
                    icon = "✅" if task["status"] == "done" else "⬜"
                    lines.append(f"{icon} {task['id']}: {task['title']}")
                self._append_message("system", "\n".join(lines))
            else:
                self._append_message("system", "Koi blueprint loaded nahi hai.")
            return True

        return False

    def _on_agent_event(self, message: str) -> None:
        # Route system/router messages into system chat and others as assistant messages.
        try:
            if message.startswith("[Router]") or message.startswith("[System]"):
                # show in chat as system message
                self._append_message("system", message)
            else:
                # show agent output as assistant message in chat
                self._append_message("assistant", message)
        except Exception:
            # defensive: if _append_message fails for some reason, at least append to agent logs
            pass

        # Always keep a full plain-text copy in agent logs for debugging
        if hasattr(self, "txt_agent_logs") and self.txt_agent_logs is not None:
            self.txt_agent_logs.append(message)
    
    def _on_load_blueprint_clicked(self) -> None:
        """Blueprint file load karo - ANY format, ANY language."""
        
        from storage.blueprint_parser import parse_blueprint_file, get_supported_extensions

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Blueprint File (Any Format)",
            "",
            get_supported_extensions(),
        )
        if not file_path:
            return

        try:
            self._append_message(
                "system",
                f"📄 Blueprint parse ho raha hai: `{os.path.basename(file_path)}`..."
            )
            self.statusBar().showMessage("Blueprint parsing... please wait", 10000)

            blueprint_data = parse_blueprint_file(file_path)

            from storage.blueprint_storage import load_blueprint
            load_blueprint(blueprint_data)

            self.btn_progress.setEnabled(True)
            title = blueprint_data.get("title", "Unknown")
            tasks_count = len(blueprint_data.get("tasks", []))
            self._append_message(
                "system",
                f"✅ **Blueprint loaded successfully!**\n"
                f"**Title:** {title}\n"
                f"**Tasks:** {tasks_count}\n"
                f"**Source:** `{os.path.basename(file_path)}`"
            )
        except Exception as exc:
            self._append_message("error", f"❌ Blueprint load failed: {exc}")

    def _extract_path_helper(self, text: str) -> str:
        """Event text se file path nikalo."""
        import re
        patterns = [
            r'[A-Z]:\\[^\s"\'\\]+(?:\\[^\s"\'\\]+)*',
            r'[A-Z]:/[^\s"\'\\]+(?:/[^\s"\'\\]+)*',
            r'[a-zA-Z_][\w/]*\.\w+',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return ""

    def _set_agent_status(self, text: str, color: str) -> None:
        """Agent status label update karta hai with color."""
        self.lbl_agent_status.setText(text)
        self.lbl_agent_status.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: bold; padding: 4px 0;"
        )
        # Window ke bottom status bar mein bhi dikhao
        self.statusBar().showMessage(text)

    def _on_agent_waiting(self, message: str) -> None:
        self._agent_tick_timer.stop()
        self.txt_agent_logs.append(f"<b style='color:orange;'>⏳ [WAITING FOR APPROVAL]</b>")
        self.txt_agent_logs.append(f"<b style='color:#FFD54F;'>  → {message}</b>")
        self.btn_approve_agent.setEnabled(True)
        self.btn_reject_agent.setEnabled(True)
        self._set_agent_status("⏳ Waiting for Your Approval", "#FFA726")
        self._append_message(
            "system",
            f"⚠️ **Agent Approval Required!**\n\n**Action:** {message}\n\n"
            "Right panel ke 'Agent Logs' tab mein Approve/Reject karein."
        )

    def _on_approve_agent_clicked(self) -> None:
        if self._agent_worker:
            self.txt_agent_logs.append("<b style='color:green;'>✅ [User] Approved. Continuing execution...</b>")
            self.btn_approve_agent.setEnabled(False)
            self.btn_reject_agent.setEnabled(False)
            self._set_agent_status("🔄 Agent Processing...", "#4f7cff")
            # 🔴 Threading fix: UI freeze nahi hoga
            import threading
            threading.Thread(target=self._agent_worker.approve_and_continue, daemon=True).start()

    def _on_reject_agent_clicked(self) -> None:
        if self._agent_worker:
            self.txt_agent_logs.append("<b style='color:red;'>❌ [User] Rejected action.</b>")
            self.btn_approve_agent.setEnabled(False)
            self.btn_reject_agent.setEnabled(False)
            self._set_agent_status("🔄 Agent Processing...", "#4f7cff")
            # 🔴 Threading fix: UI freeze nahi hoga
            import threading
            threading.Thread(
                target=lambda: self._agent_worker.reject_pending("User rejected the action via UI"),
                daemon=True
            ).start()

    def _on_kill_agent_clicked(self) -> None:
        if self._agent_worker:
            self.txt_agent_logs.append("<b style='color:orange;'>⏹ [User] Kill requested. Pausing agent...</b>")
            self.btn_kill_agent.setEnabled(False)
            self.btn_approve_agent.setEnabled(False)
            self.btn_reject_agent.setEnabled(False)
            # 🔴 Threading fix: UI freeze nahi hoga
            import threading
            threading.Thread(target=self._agent_worker.kill, daemon=True).start()

    def _on_agent_finished(self, message: str) -> None:
        self.txt_agent_logs.append(f"\n🎉 DONE: {message}")
        self.txt_agent_logs.append("─" * 50 + "\n")

        if self._last_agent_text:
            self._append_message("assistant", self._last_agent_text)
            self._last_agent_text = ""
        else:
            self._append_message("system", f"✅ **Agent Task Completed** — {message}")

        self._set_agent_status("✅ Agent Finished", "#66BB6A")
        self._cleanup_agent_worker()

    def _on_agent_failed(self, message: str) -> None:
        """Agent failed - error summary chat mein dikhao."""
        self.txt_agent_logs.append(f"<b style='color:red;'>💥 [FAILED] {message}</b>")
        
        # ❌ Error summary chat window mein
        error_summary = (
            f"❌ **Agent Task Failed!**\n\n"
            f"**Error:** {message}\n\n"
            f"Kuch technical problem aa gayi. "
            f"Aap dobara try kar sakte hain ya task change kar sakte hain."
        )
        self._append_message("error", error_summary)
        
        # UI state reset
        self._set_agent_status("❌ Agent Failed", "#EF5350")
        self._cleanup_agent_worker()

    def _check_semantic_search_status(self) -> None:
        """ChromaDB available hai ya nahi - UI mein dikhao."""
        try:
            import chromadb
            import sentence_transformers
            self.lbl_search_mode.setText("🧠 Semantic: ON")
            self.lbl_search_mode.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.lbl_search_mode.setToolTip(
                "ChromaDB semantic search active hai.\n"
                "Meaning-based search (e.g., 'password hashing kahan hai') kaam karega."
            )
        except ImportError:
            self.lbl_search_mode.setText("🔤 Semantic: OFF")
            self.lbl_search_mode.setStyleSheet("color: #FF9800; font-weight: bold;")
            self.lbl_search_mode.setToolTip(
                "ChromaDB installed nahi hai.\n"
                "Sirf keyword search kaam kar raha hai.\n\n"
                "Install karne ke liye:\n"
                "pip install chromadb sentence-transformers"
            )

    def _cleanup_agent_worker(self) -> None:
        self._agent_tick_timer.stop()
        self.btn_start_agent.setEnabled(True)
        self.btn_approve_agent.setEnabled(False)
        self.btn_reject_agent.setEnabled(False)
        self.btn_kill_agent.setEnabled(False)
        self._set_agent_status("⚪ Agent Idle", "#9aa1b5")
        self._agent_worker = None