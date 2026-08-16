"""
ui/query_worker.py
Smart Chat Assistant Worker - ERP-AI-Tool.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from llm_router import ask_llm_with_history
from memory_index import MemoryIndex
from tools.web_search import search_web

logger = logging.getLogger(__name__)

MEMORY_FILE_NAME = "erp_memory.json"
PROJECT_CONFIG_DIR = "projects"

MAX_CONTEXT_FILES = 10
MAX_HISTORY_MESSAGES = 8

_STOPWORDS = {
    "the", "is", "are", "how", "what", "why", "when", "where", "kaise",
    "kya", "hai", "hain", "ka", "ki", "ke", "mein", "se", "aur", "for",
    "and", "this", "that", "with", "does", "do", "please",
    "batao", "bata", "karo", "kar",
}

GENERIC_PERSONA_BLOCK = """
You reason as a Senior Software Architect.
""".strip()

DUAL_PERSONA_BLOCK = """
You have two expert personas fused into one:
1. Chartered Accountant / Finance Auditor
2. Senior Software Architect
""".strip()

BASE_PROMPT_TEMPLATE = """
You are a Senior AI Colleague inside ERP-AI-Tool.
Project: {project_name}

=========================================================
CRITICAL RULES (NON-NEGOTIABLE)
=========================================================
1. USE YOUR JUDGMENT: Understand the user's actual intent from context, don't force rigid keyword-to-answer mappings. For example, if they ask about "APIs for coding" in the context of this tool's own setup, they likely mean LLM/AI model APIs — but read the actual question and conversation before assuming. If genuinely ambiguous, ask a quick clarifying question instead of guessing wrong.
2. TOOL AWARENESS: You know ERP-AI-Tool scans any project folder regardless of which editor (VS Code, PyCharm, etc.) created it — just select the folder and scan. Use this knowledge naturally when relevant, don't wait for exact keyword matches to trigger it.

3. WEB SEARCH: If "LIVE WEB SEARCH RESULTS" section is present in the 
   user's message, use it to answer current/live questions — you may 
   say "web search ke hisaab se". If that section is ABSENT, you cannot 
   browse the web — say "main abhi web search nahi kar paya" instead of 
   guessing or inventing facts.
3. NO DUMMY FILES: NEVER propose creating new files unless explicitly asked.
4. NO FAKE URLS: Never invent URLs or links.
5. HONESTY: If unsure, say "I am not 100% sure".
6. BREVITY: Simple question = Simple answer (1-3 lines). Never repeat the question. Never over-explain. No unnecessary context.
7. SELF-AWARENESS: You run INSIDE ERP-AI-Tool. When asked "humara kaun sa API hai" or "current setup kya hai", answer about THIS tool's config: Chat = Groq primary → OpenRouter fallback. Agent = OpenRouter primary → Groq fallback. Gemini = disabled. Do NOT confuse with the scanned project (Medical-ERP-V2).
8. BE DECISIVE: When user asks "which is best", give ONE clear recommendation with reasoning. Never say "it depends on use case" without giving a specific answer first.

=========================================================
HUMAN-LIKE CONVERSATION STYLE
=========================================================
- Talk like a real senior developer colleague sitting next to Bijay, not like a customer-support bot.
- Vary sentence length naturally — mix short punchy lines with a longer explanatory one when needed. Don't make every response a rigid bullet list; use plain sentences for simple answers, bullets only when listing 3+ distinct items.
- Have a mild personality: if something in the code is genuinely messy or risky, say so plainly ("ye thoda risky hai" / "isme dikkat aa sakti hai") instead of neutral corporate hedging.
- Don't restate what the user already said back to them before answering.
- Skip disclaimers like "As an AI..." or "I don't have real-time access..." — just answer directly within known limits.
- If the answer has some uncertainty, say it in one natural clause ("pakka nahi bol sakta, but...") instead of a formal caveat paragraph.
- React contextually — if the user shares a bug, acknowledge it in one short phrase before diving into the fix, the way a colleague would ("haan ye galat hai, dekhte hain") — but don't do this for every single message, only when it fits naturally.

{persona_block}

{glossary_block}
PROJECT RULES:
{rules_block}
""".strip()


def _load_project_config(project_folder_path: str | None) -> dict | None:
    if not project_folder_path:
        return None

    folder_name = os.path.basename(project_folder_path.rstrip("/\\")).lower()
    normalized_folder = folder_name.replace("-", "_").replace(" ", "_")

    if not os.path.isdir(PROJECT_CONFIG_DIR):
        return None

    try:
        filenames = os.listdir(PROJECT_CONFIG_DIR)
    except OSError:
        return None

    for filename in filenames:
        if not filename.endswith(".json"):
            continue

        stem = filename[:-5].lower()

        if stem in normalized_folder or normalized_folder in stem:
            full_path = os.path.join(PROJECT_CONFIG_DIR, filename)
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return None

    return None


def _build_glossary_block(glossary_items: list) -> str:
    if not glossary_items:
        return ""

    lines = ["PROJECT DOMAIN GLOSSARY:"]
    for item in glossary_items:
        term = str(item.get("term", "")).strip()
        meaning = str(item.get("meaning", "")).strip()
        if term and meaning:
            lines.append(f"- {term}: {meaning}")

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def _build_rules_block(rules: list) -> str:
    if not rules:
        return "- No project-specific architecture rules configured."

    lines = []
    for rule in rules:
        rule_text = str(rule).strip()
        if rule_text:
            lines.append(f"- {rule_text}")

    if not lines:
        return "- No project-specific architecture rules configured."
    return "\n".join(lines)


def _build_system_prompt(project_folder_path: str | None) -> str:
    config = _load_project_config(project_folder_path) or {}

    project_name = (
        config.get("project_name")
        or (os.path.basename(project_folder_path) if project_folder_path else "")
        or "Current Project"
    )

    persona_block = (
        DUAL_PERSONA_BLOCK
        if config.get("personas")
        else GENERIC_PERSONA_BLOCK
    )

    glossary_block = _build_glossary_block(config.get("domain_glossary", []))
    rules_block = _build_rules_block(config.get("architecture_rules", []))

    return BASE_PROMPT_TEMPLATE.format(
        project_name=project_name,
        persona_block=persona_block,
        glossary_block=glossary_block,
        rules_block=rules_block,
    )

def _needs_web_search(query: str, memory: MemoryIndex) -> bool:
    """
    SMART RULE: Pehle codebase mein dhundo (including function/class names).
    Agar project se related sawal hai toh web search MAT karo.
    """
    keywords = _extract_keywords(query)
    for keyword in keywords:
        if memory.search(keyword):
            return False  # Codebase mein match mil gaya

    # Function/class names bhi check karo
    query_lower = query.lower()
    for file_path in memory.list_all_files():
        summary = memory.get_file_summary(file_path)
        if summary:
            for func in summary.get("functions", []):
                if func["name"].lower() in query_lower:
                    return False
            for cls in summary.get("classes", []):
                if cls["name"].lower() in query_lower:
                    return False
    return True  # Project mein nahi mila, web search karo

def _extract_keywords(query: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", query.lower())
    cleaned = [word for word in words if word not in _STOPWORDS]
    return cleaned[:10]


def _format_module_line(module: dict) -> str:
    parts = [f"- {module.get('file', 'unknown')} ({module.get('type', '?')})"]

    if module.get("classes"):
        parts.append("classes: " + ", ".join(module["classes"]))

    if module.get("functions"):
        parts.append("functions: " + ", ".join(module["functions"]))

    if module.get("tables"):
        parts.append("tables: " + ", ".join(module["tables"]))

    return " | ".join(parts)


def _build_context(memory: MemoryIndex, query: str) -> str:
    """
    Enhanced context builder:
    Layer 1: Semantic search (ChromaDB)
    Layer 2: Keyword search + ACTUAL CODE SNIPPETS
    Layer 3: Function-level code extraction
    Layer 4: Import graph (dependency queries ke liye)
    """
    context_parts = []

    # ─── Layer 1: Semantic Search (ChromaDB) ───
    try:
        from chroma_memory import ChromaMemory
        chroma = ChromaMemory(storage_dir="./erp_chroma_memory")
        semantic_results = chroma.semantic_search(query, top_k=5)
        if semantic_results:
            lines = ["🔍 SEMANTIC SEARCH RESULTS (ChromaDB - meaning-based):"]
            for r in semantic_results:
                lines.append(f"- {r['file']} (relevance: {r.get('relevance_score', 'N/A')})")
                if r.get('summary'):
                    lines.append(f"  {r['summary'][:200]}")
            context_parts.append("\n".join(lines))
    except ImportError:
        context_parts.append("⚠️ [Semantic Search: OFF - ChromaDB not installed. Using keyword search only.]")
    except Exception:
        context_parts.append("⚠️ [Semantic Search: ERROR - Falling back to keyword search.]")

    # ─── Layer 2: Keyword Search + Code Snippets ───
    keywords = _extract_keywords(query)
    matched_files: dict[str, dict] = {}

    for keyword in keywords:
        try:
            search_results = memory.search(keyword)
        except Exception:
            continue
        for hit in search_results:
            file_path = hit.get("file")
            if not file_path or file_path in matched_files:
                continue
            summary = memory.get_file_summary(file_path)
            if summary:
                matched_files[file_path] = summary
        if len(matched_files) >= MAX_CONTEXT_FILES:
            break

    if not matched_files:
        overview = memory.get_project_overview()
        if overview.get("total_files", 0) == 0:
            return "No project scanned yet. Answer using general expertise."
        lines = [
            "No exact keyword match found. Project overview for awareness:",
            f"Project: {overview.get('project_root', 'Unknown')}",
            f"Total indexed files: {overview.get('total_files', 0)}",
        ]
        for module in overview.get("modules", [])[:MAX_CONTEXT_FILES]:
            lines.append(_format_module_line(module))
        context_parts.append("\n".join(lines))
    else:
        # Structure summary
        lines = [f"📂 Relevant project files ({len(matched_files)}):"]
        for file_path, summary in matched_files.items():
            lines.append(
                _format_module_line({
                    "file": file_path,
                    "type": summary.get("file_type"),
                    "classes": [c["name"] for c in summary.get("classes", [])],
                    "functions": [f["name"] for f in summary.get("functions", [])],
                    "tables": summary.get("sql_tables", []),
                })
            )
        context_parts.append("\n".join(lines))

        # 🆕 ACTUAL CODE SNIPPETS (Top 3 files, 50 lines each)
        code_lines = ["\n📝 ACTUAL CODE SNIPPETS (top matched files):"]
        code_files_added = 0
        for file_path in list(matched_files.keys())[:3]:
            code = memory.get_code_snippet(file_path, max_lines=50)
            if code:
                code_lines.append(f"\n--- {file_path} ---")
                code_lines.append(f"```python\n{code}\n```")
                code_files_added += 1
        if code_files_added > 0:
            context_parts.append("\n".join(code_lines))

    # ─── Layer 3: Function-Level Extraction ───
    query_lower = query.lower()
    func_name_found = None
    func_file_found = None

    # Check if user mentioned a specific function
    for file_path, summary in matched_files.items():
        for func in summary.get("functions", []):
            if func["name"].lower() in query_lower:
                func_name_found = func["name"]
                func_file_found = file_path
                break
        for cls in summary.get("classes", []):
            for method in cls.get("methods", []):
                if method["name"].lower() in query_lower:
                    func_name_found = method["name"]
                    func_file_found = file_path
                    break
            if func_name_found:
                break
        if func_name_found:
            break

    if func_name_found and func_file_found:
        func_code = memory.get_function_code(func_file_found, func_name_found)
        if func_code:
            context_parts.append(
                f"\n🔧 FUNCTION CODE: `{func_name_found}` in `{func_file_found}`:\n"
                f"```python\n{func_code}\n```"
            )

    # ─── Layer 4: Import Graph (dependency queries) ───
    dependency_keywords = ["import", "use karta", "call karta", "depend", "kaun", "where is", "kahan", "kon si file"]
    if any(kw in query_lower for kw in dependency_keywords):
        graph = memory.get_import_graph()
        if graph:
            graph_lines = ["\n🔗 IMPORT GRAPH (file dependencies):"]
            for file_path, imports in list(graph.items())[:10]:
                graph_lines.append(f"  {file_path} → imports: {', '.join(imports[:5])}")
            # Reverse imports bhi dikhao agar specific file puchi gayi
            for file_path in matched_files:
                reverse = memory.get_reverse_imports(file_path)
                if reverse:
                    graph_lines.append(f"  ← {file_path} ko import karte hain: {', '.join(reverse)}")
            context_parts.append("\n".join(graph_lines))

    return "\n\n".join(context_parts)


class QueryWorker(QThread):
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        user_query: str,
        history: Optional[list[dict]] = None,
        parent: Optional[object] = None,
    ) -> None:
        super().__init__(parent)
        self._user_query = user_query
        self._history = history or []

    def run(self) -> None:
        try:
            text = self._user_query.strip()

            if not text:
                self.failed.emit("Query empty hai.")
                return

            memory = MemoryIndex(MEMORY_FILE_NAME)
            
            command_answer = self._handle_blueprint_command(text, memory)
            if command_answer is not None:
                self.finished_ok.emit(command_answer)
                return

            system_prompt = _build_system_prompt(memory.project_root_path)
            context = _build_context(memory, text)

            # 🆕 Agar query ko live web info chahiye lagta hai, seedha yahin
            # se search karo - Agent/Terminal ki zaroorat nahi
            web_context = ""
            if _needs_web_search(text, memory):
                try:
                    search_results = search_web(text, max_results=3)
                    web_context = f"\n\nLIVE WEB SEARCH RESULTS:\n{search_results}"
                except Exception as exc:
                    logger.warning("Chat web search failed: %s", exc)
                    web_context = "\n\n(Web search attempt fail ho gaya, training data se jawab de raha hoon.)"

            latest_user_content = (
                "CODEBASE CONTEXT:\n"
                f"{context}"
                f"{web_context}\n\n"
                "USER QUERY:\n"
                f"{text}"
            )

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self._history[-MAX_HISTORY_MESSAGES:])
            messages.append({"role": "user", "content": latest_user_content})

            answer = ask_llm_with_history(messages)

            if not answer:
                self.failed.emit("LLM se empty response aaya.")
                return

            self.finished_ok.emit(answer)

        except Exception as exc:
            logger.exception("QueryWorker failed.")
            self.failed.emit(f"Query failed: {exc}")

    def _handle_blueprint_command(self, text: str, memory: MemoryIndex) -> Optional[str]:
        """
        Faster, safer intent detection for blueprint commands.
        First use local keyword heuristics; if ambiguous, fall back to ask_llm().
        Returns a reply string if the text is handled as a blueprint command; otherwise None.
        """
        from storage.blueprint_storage import get_active_blueprint

        blueprint = get_active_blueprint()
        lower = text.strip().lower()

        # Quick local heuristics
        if any(kw in lower for kw in ("blueprint status", "bp status", "progress", "status of blueprint")):
            try:
                from storage.blueprint_storage import get_progress_report
                report = get_progress_report()
                if memory.project_root_path and blueprint:
                    report += "\n\n" + self._auto_detect_progress(blueprint, memory.project_root_path)
                return report
            except Exception as exc:
                return f"Blueprint status failed: {exc}"

        if any(kw in lower for kw in ("blueprint tasks", "bp tasks", "list tasks", "tasks list")):
            try:
                if not blueprint:
                    return "Koi active blueprint loaded nahi hai."
                lines = [f"📋 {blueprint.get('title', 'Unknown')}", ""]
                for task in blueprint.get("tasks", []):
                    icon = "✅" if task["status"] == "done" else "⬜"
                    module = task.get("module", "")
                    module_tag = f" [{module}]" if module and module != "General" else ""
                    lines.append(f"{icon} {task['id']}: {task['title']}{module_tag}")
                return "\n".join(lines)
            except Exception as exc:
                return f"Blueprint tasks failed: {exc}"

        if any(kw in lower for kw in ("blueprint compare", "bp compare", "compare blueprint", "compare tasks")):
            project_root = memory.project_root_path
            if not project_root:
                return "Pehle project folder select aur scan karo."
            try:
                from storage.blueprint_storage import compare_with_repo
                return compare_with_repo(project_root)
            except Exception as exc:
                return f"Blueprint compare failed: {exc}"

        # If none of the heuristics matched, optionally consult the LLM only if short and ambiguous
        # Use LLM as a last resort (keeps costs down)
        try:
            # small heuristic: only call LLM for single-sentence ambiguous commands under 120 chars
            if len(text) < 120 and ("\n" not in text) and (len(text.split()) < 12):
                from llm_router import ask_llm
                prompt = f"""User input: {text}

    Classify this into one of exactly these tokens (no extra text):
    - blueprint_status
    - blueprint_tasks
    - blueprint_compare
    - chat

    Return only the token."""
                intent_raw = ask_llm(prompt).strip().lower().split()
                if intent_raw:
                    intent = intent_raw[0]
                    # Reuse above logic
                    if intent == "blueprint_status":
                        try:
                            from storage.blueprint_storage import get_progress_report
                            report = get_progress_report()
                            if memory.project_root_path and blueprint:
                                report += "\n\n" + self._auto_detect_progress(blueprint, memory.project_root_path)
                            return report
                        except Exception as exc:
                            return f"Blueprint status failed: {exc}"
                    if intent == "blueprint_tasks":
                        try:
                            if not blueprint:
                                return "Koi active blueprint loaded nahi hai."
                            lines = [f"📋 {blueprint.get('title', 'Unknown')}", ""]
                            for task in blueprint.get("tasks", []):
                                icon = "✅" if task["status"] == "done" else "⬜"
                                module = task.get("module", "")
                                module_tag = f" [{module}]" if module and module != "General" else ""
                                lines.append(f"{icon} {task['id']}: {task['title']}{module_tag}")
                            return "\n".join(lines)
                        except Exception as exc:
                            return f"Blueprint tasks failed: {exc}"
                    if intent == "blueprint_compare":
                        project_root = memory.project_root_path
                        if not project_root:
                            return "Pehle project folder select aur scan karo."
                        try:
                            from storage.blueprint_storage import compare_with_repo
                            return compare_with_repo(project_root)
                        except Exception as exc:
                            return f"Blueprint compare failed: {exc}"
        except Exception:
            # If LLM classification fails, continue to normal chat flow (no blocking)
            return None

        # Not a blueprint-specific command
        return None

    def _auto_detect_progress(self, blueprint: dict, project_root: str) -> str:
        """
        Level 2 Auto-Detection: File exist + function exist check.
        Blueprint tasks ko actual files se match karo.
        """
        import os as os_mod
        import ast

        lines = ["🔍 **Auto-Detection Results:**"]
        for task in blueprint.get("tasks", []):
            expected_file = task.get("file", "")
            expected_func = task.get("expected_function", "")

            if not expected_file:
                continue

            full_path = os_mod.path.join(project_root, expected_file)

            if not os_mod.isfile(full_path):
                if task["status"] == "done":
                    lines.append(f"  ⚠️ {task['id']}: Marked done but file MISSING: `{expected_file}`")
                else:
                    lines.append(f"  ⬜ {task['id']}: File not found: `{expected_file}`")
                continue

            # File exist hai - function check karo
            if expected_func:
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        tree = ast.parse(f.read())
                    func_names = set()
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            func_names.add(node.name)
                        elif isinstance(node, ast.ClassDef):
                            func_names.add(node.name)

                    if expected_func in func_names:
                        lines.append(f"  ✅ {task['id']}: `{expected_file}` + `{expected_func}()` found")
                    else:
                        lines.append(f"  🔄 {task['id']}: File exists but `{expected_func}()` NOT found")
                except Exception:
                    lines.append(f"  🔄 {task['id']}: `{expected_file}` exists (parse error)")
            else:
                lines.append(f"  ✅ {task['id']}: `{expected_file}` exists")

        if len(lines) == 1:
            return ""  # Koi detectable task nahi
        return "\n".join(lines)