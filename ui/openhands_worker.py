# Updated: ui/openhands_worker.py
"""
ui/openhands_worker.py - updated timeout, clearer comments, small robustness fixes.

Notes:
- Unified configurable timeout: default 60 seconds, can be overridden with OPENHANDS_TIMEOUT env var.
- Clearer inline comments and safer timer handling.
"""
from __future__ import annotations
import logging
import os
import time
from typing import Optional
import signal
import threading

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from PyQt6.QtCore import QThread, pyqtSignal

# Keep imports lazy for environments that don't have openhands/sdk installed
try:
    from openhands.sdk import LLM, Agent, Conversation, Tool
    from openhands.sdk.conversation.state import ConversationExecutionStatus
    from openhands.sdk.event.base import Event
    from openhands.sdk.security.confirmation_policy import NeverConfirm, AlwaysConfirm
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.terminal import TerminalTool
except Exception:
    # Running without SDK will still allow the UI to import this module safely.
    LLM = Agent = Conversation = Tool = Event = ConversationExecutionStatus = None
    NeverConfirm = AlwaysConfirm = None
    FileEditorTool = TerminalTool = None

logger = logging.getLogger(__name__)

# Default fallback chain (kept as-is, but stable)
FREE_MODELS = [
    ("Groq-Llama-70B", "groq/llama-3.3-70b-versatile"),
    ("Nemotron-Lightning", "openrouter/nvidia/nemotron-3.5-lightning:free"),
    ("Nemotron-Ultra-550B", "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"),
    ("Gemma-4-31B", "openrouter/google/gemma-4-31b-it:free"),
    ("Nemotron-Super-120B", "openrouter/nvidia/nemotron-3-super-120b-a12b:free"),
    ("Gemma-4-26B", "openrouter/google/gemma-4-26b-a4b-it:free"),
    ("North-Mini-Code", "openrouter/cohere/north-mini-code:free"),
]

# Timeout config (seconds) — default 60s; override with OPENHANDS_TIMEOUT env var if needed.
DEFAULT_AGENT_TIMEOUT_SECONDS = int(os.getenv("OPENHANDS_TIMEOUT", "60"))


def _build_llm(model: str, api_key: str) -> LLM:
    return LLM(
        model=model,
        api_key=api_key,
        num_retries=1,
        retry_min_wait=1,
        retry_max_wait=3,
        timeout=20,  # per-request HTTP timeout
    )


def _build_agent(llm: LLM) -> Agent:
    return Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name) if TerminalTool else None,
            Tool(name=FileEditorTool.name) if FileEditorTool else None,
        ],
    )


class OpenHandsWorker(QThread):
    event_received = pyqtSignal(str)
    waiting_for_confirmation = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        workspace_path: str,
        user_instruction: str,
        parent: Optional[object] = None,
    ) -> None:
        super().__init__(parent)
        self._workspace_path = workspace_path
        self._user_instruction = user_instruction
        self._conversation: Optional[Conversation] = None
        self._last_action_summary: str = ""
        # Unified timeout configuration (default 60s). Use env OPENHANDS_TIMEOUT to override.
        self._timeout_seconds: int = DEFAULT_AGENT_TIMEOUT_SECONDS
        self._timed_out: bool = False
        self._last_emitted_line: str = ""
        self._repeat_count: int = 0
        self._first_approval_done: bool = False

    def _start_timeout_timer(self) -> threading.Timer:
        """
        Start a background timer that marks the worker as timed out if no agent response.
        This timer is daemonized and will be cancelled when the conversation completes.
        """
        def _timeout_handler():
            self._timed_out = True
            self.event_received.emit(f"⏰ [Timeout] {self._timeout_seconds}s - no response. Trying next model...")
            if self._conversation:
                try:
                    self._conversation.pause()
                except Exception:
                    pass

        timer = threading.Timer(self._timeout_seconds, _timeout_handler)
        timer.daemon = True
        timer.start()
        return timer

    # Event handling remains largely the same; keep concise and robust
    def _on_agent_event(self, event: Event) -> None:
        try:
            summary = str(event)
        except Exception:
            summary = f"<unprintable event: {type(event).__name__}>"

        if "ActionEvent" in summary:
            action_type = self._extract_action_type(summary)
            self._last_action_summary = action_type
            if action_type == self._last_emitted_line:
                self._repeat_count += 1
                return
            else:
                if self._repeat_count > 0:
                    self.event_received.emit(f"     (...{self._repeat_count} more similar) ")
                self._repeat_count = 0
                self._last_emitted_line = action_type
                self.event_received.emit(f"  → {action_type}")
        elif "ObservationEvent" in summary:
            if "created successfully" in summary.lower() or "file created" in summary.lower():
                path = self._extract_path_from_event(summary)
                self.event_received.emit(f"  ✅ File created: {path}" if path else "  ✅ File created")
            elif "error" in summary.lower() or "not recognized" in summary.lower():
                error_snippet = summary[:300].replace("\n", " ")
                self.event_received.emit(f"  ❌ Command failed: {error_snippet}")
        # Else ignore noisy events

    def _extract_action_type(self, event_str: str) -> str:
        if "FileEditorAction" in event_str:
            details = self._extract_file_editor_details(event_str)
            if details:
                return details
            return "📝 File Editor — requested file operation"
        if "TerminalAction" in event_str or "CmdRunAction" in event_str:
            return "💻 Terminal — command execution requested"
        if "FinishAction" in event_str:
            return "🏁 Finish — agent intends to finish"
        return f"⚙️ Action: {event_str[:150]}"

    def _extract_file_editor_details(self, event_str: str) -> str:
        try:
            full_text = event_str.lower()
            path = self._extract_path_from_event(event_str)
            path_str = f" `{path}`" if path else ""
            if "view" in full_text or "cat -n" in full_text:
                return f"👁️ File Read —{path_str} file read requested"
            if "created successfully" in full_text or ("create" in full_text and "path" in full_text):
                return f"📝 File Create —{path_str} file create requested"
            if "edit" in full_text or "insert" in full_text or "str_replace" in full_text:
                return f"✏️ File Edit —{path_str} edit requested"
            if "delete" in full_text or "remove" in full_text:
                return f"🗑️ File Delete —{path_str} delete requested"
            if path:
                return f"📝 File Operation — requested on{path_str}"
        except Exception:
            pass
        return ""

    def _extract_path_from_event(self, event_str: str) -> str:
        import re
        patterns = [
            r'[A-Z]:\\[^\s"\'\\]+(?:\\[^\s"\'\\]+)*',
            r"/[a-zA-Z][^\s'\"]+/[^\s'\"]+",
            r"[a-zA-Z_][\w/]*\.\w+",
        ]
        for pattern in patterns:
            match = re.search(pattern, event_str)
            if match:
                return match.group(0)
        return ""

    # Run loop with model fallback and robust timeout handling
    def run(self) -> None:
        # Check keys - minimally require either OpenRouter or Groq
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")
        if not openrouter_key and not groq_key:
            self.failed.emit("GROQ_API_KEY ya OPENROUTER_API_KEY .env mein nahi mili.")
            return

        workspace = self._workspace_path or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.event_received.emit(f"[System] Using workspace: {workspace}")

        models = FREE_MODELS  # simple reuse of constant

        last_error: Optional[Exception] = None

        for model_name, model_slug in models:
            # small optimization: skip if keys clearly do not match model provider
            api_key_to_use = groq_key if model_slug.startswith("groq/") else openrouter_key
            if not api_key_to_use:
                self.event_received.emit(f"⏭️ {model_name} skipped — API key missing")
                continue

            try:
                self.event_received.emit(f"🔄 Trying: {model_name}...")
                llm = _build_llm(model_slug, api_key_to_use)
                agent = _build_agent(llm)

                # Tool scripts path (safe path construction)
                tool_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                web_search_script = os.path.join(tool_root, "tools", "web_search.py").replace("\\", "/")
                repo_reader_script = os.path.join(tool_root, "tools", "repo_reader.py").replace("\\", "/")

                tools_instruction = f"""
AVAILABLE TOOL SCRIPTS:
- Web Search: python "{web_search_script}" "your query"
- Repo Reader: python "{repo_reader_script}" read <file>
"""

                self._conversation = Conversation(
                    agent=agent,
                    workspace=workspace,
                    callbacks=[self._on_agent_event],
                    visualizer=None,
                )

                # confirmation policy: first run may use AlwaysConfirm; after user approves, switch to NeverConfirm
                if self._first_approval_done and NeverConfirm:
                    self._conversation.set_confirmation_policy(NeverConfirm())
                elif AlwaysConfirm:
                    self._conversation.set_confirmation_policy(AlwaysConfirm())

                # Inject blueprint context only if the user asked for blueprint related ops
                try:
                    from storage.blueprint_storage import get_active_blueprint, get_progress_report
                    active_bp = get_active_blueprint()
                    user_text = str(self._user_instruction) if self._user_instruction else ""
                    use_blueprint = False
                    if active_bp and any(k in user_text.lower() for k in ("blueprint", "progress", "status", "t0", "task")):
                        use_blueprint = True

                    if use_blueprint:
                        bp_context = get_progress_report()
                        full_instruction = f"📋 ACTIVE BLUEPRINT CONTEXT:\n{bp_context}\n\n{tools_instruction}\n📝 USER TASK:\n{user_text}\n"
                    else:
                        full_instruction = f"{tools_instruction}\n📝 USER TASK:\n{user_text}\n"
                except Exception:
                    user_text = str(self._user_instruction) if self._user_instruction else ""
                    full_instruction = f"{tools_instruction}\n📝 USER TASK:\n{user_text}\n"

                self._conversation.send_message(full_instruction)
                timer = self._start_timeout_timer()

                self._conversation.run()

                # cancel timer once the run returns
                try:
                    timer.cancel()
                except Exception:
                    pass

                if self._timed_out:
                    # timed out on this model, try next
                    last_error = RuntimeError("Agent timeout")
                    self.event_received.emit(f"⏭️ {model_name} timed out — trying next model...")
                    # reset timed-out flag for next model
                    self._timed_out = False
                    continue

                status = self._conversation.state.execution_status
                if status == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION:
                    detail = self._last_action_summary or "Unknown action"
                    self.waiting_for_confirmation.emit(detail)
                    return
                elif status == ConversationExecutionStatus.ERROR:
                    last_error = RuntimeError("Agent returned ERROR status")
                    self.event_received.emit(f"⏭️ {model_name} returned ERROR — trying next model...")
                    continue
                elif status == ConversationExecutionStatus.STUCK:
                    last_error = RuntimeError("Agent stuck")
                    self.event_received.emit(f"⏭️ {model_name} seems stuck — trying next model...")
                    continue
                else:
                    self.finished_ok.emit(f"✅ {model_name} completed. Status: {status}")
                    return

            except Exception as exc:
                logger.exception("OpenHandsWorker: model attempt failed.")
                last_error = exc
                self.event_received.emit(f"⏭️ {model_name} busy/failed — trying next model...")
                continue

        # All models exhausted
        self.failed.emit(f"Agent run failed on all models. Last error: {last_error}")

    # Confirmation controls (unchanged but robust)
    def is_waiting_for_confirmation(self) -> bool:
        if self._conversation is None:
            return False
        try:
            return (
                self._conversation.state.execution_status
                == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
            )
        except Exception:
            return False

    def approve_and_continue(self) -> None:
        if self._conversation is None:
            return
        try:
            if not self._first_approval_done:
                self._first_approval_done = True
                if NeverConfirm:
                    self._conversation.set_confirmation_policy(NeverConfirm())
                self.event_received.emit("[Approval] ✅ Trust granted. Agent now has reduced confirmation requirements.")
            else:
                self.event_received.emit("[Approval] Continuing execution...")
            self._conversation.run()
            status = self._conversation.state.execution_status
            if status == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION:
                detail = self._last_action_summary or "Unknown action"
                self.waiting_for_confirmation.emit(detail)
            elif status in (ConversationExecutionStatus.ERROR, ConversationExecutionStatus.STUCK):
                self.failed.emit(f"Agent entered {status} after approval.")
            else:
                self.finished_ok.emit(f"Agent continued after approval. Status: {status}")
        except Exception as exc:
            logger.exception("approve_and_continue failed.")
            self.failed.emit(f"Approve/continue failed: {exc}")

    def reject_pending(self, reason: str = "User rejected the action") -> None:
        if self._conversation is None:
            return
        try:
            self._conversation.reject_pending_actions(reason)
            self.event_received.emit(f"[Approval] Rejected: {reason}")
            self._conversation.run()
            status = self._conversation.state.execution_status
            if status == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION:
                self.waiting_for_confirmation.emit("Agent proposed another action after rejection.")
            elif status in (ConversationExecutionStatus.ERROR, ConversationExecutionStatus.STUCK):
                self.failed.emit(f"Agent entered {status} after rejection.")
            else:
                self.finished_ok.emit(f"Agent finished after rejection. Status: {status}")
        except Exception as exc:
            logger.exception("reject_pending failed.")
            self.failed.emit(f"Reject failed: {exc}")

    def kill(self) -> None:
        if self._conversation is None:
            return
        try:
            self._conversation.pause()
            self.event_received.emit("[Control] Agent paused by user.")
        except Exception as exc:
            logger.exception("kill/pause failed.")
            self.failed.emit(f"Pause failed: {exc}")


__all__ = ["OpenHandsWorker"]