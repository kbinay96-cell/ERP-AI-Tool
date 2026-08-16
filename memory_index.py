"""
memory_index.py

Memory/Index Layer - Option A (Local JSON)
---------------------------------------------------------
Purpose:
    Persists the Codebase Reader's output (FileSummary list)
    to a local JSON file, so the project's structure does not
    need to be re-scanned from scratch every time.

    - 100% offline. No API. No external dependency.
    - Incremental: only re-scans files whose content changed
      (detected via hash), so repeated runs are fast.
    - Provides simple keyword search over the stored memory,
      so a query like "search_customers" or "date_engine"
      instantly returns which files/functions/classes match -
      without needing any AI model at all.

Storage format: a single JSON file, e.g. `erp_memory.json`.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from codebase_scanner import FileSummary, scan_project, scan_file


class MemoryIndex:
    """Manages the local JSON memory file for one project."""

    def __init__(self, memory_file_path: str) -> None:
        self.memory_file_path = Path(memory_file_path)
        self._data: dict = {
            "project_root": None,
            "last_scanned_at": None,
            "files": {},  # file_path -> FileSummary dict
        }
        if self.memory_file_path.exists():
            self._load()

    @property
    def project_root_path(self) -> str | None:
        """Scanned project ka root folder path - public accessor, taaki
        doosre modules (jaise query_worker.py) private self._data ko
        seedha na chhuen."""
        return self._data.get("project_root")

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        try:
            with open(self.memory_file_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Corrupted or unreadable memory file - start fresh rather
            # than crash the tool. The next build_index() call will
            # rebuild it correctly.
            self._data = {"project_root": None, "last_scanned_at": None, "files": {}}

    def save(self) -> None:
        self.memory_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Building / updating the index
    # ------------------------------------------------------------------ #
    def build_full_index(self, project_root: str) -> None:
        """Full scan - use this the first time, or with force_rebuild."""
        summaries = scan_project(project_root)
        self._data["project_root"] = str(Path(project_root).resolve())
        self._data["last_scanned_at"] = datetime.now(timezone.utc).isoformat()
        self._data["files"] = {s.file_path: s.to_dict() for s in summaries}
        self.save()

    def update_index_incremental(self, project_root: str) -> dict:
        """
        Re-scans only files that are new or changed since the last
        save (compared by content hash), and drops entries for files
        that no longer exist. Returns a small report of what changed.
        """
        root = Path(project_root).resolve()
        current_summaries = scan_project(project_root)
        current_by_path = {s.file_path: s for s in current_summaries}

        old_files = self._data.get("files", {})
        added, updated, removed = [], [], []

        for path, summary in current_by_path.items():
            old_entry = old_files.get(path)
            if old_entry is None:
                added.append(path)
            elif old_entry.get("file_hash") != summary.file_hash:
                updated.append(path)

        for path in old_files.keys():
            if path not in current_by_path:
                removed.append(path)

        self._data["project_root"] = str(root)
        self._data["last_scanned_at"] = datetime.now(timezone.utc).isoformat()
        self._data["files"] = {s.file_path: s.to_dict() for s in current_summaries}
        self.save()

        return {"added": added, "updated": updated, "removed": removed}

    # ------------------------------------------------------------------ #
    # Reading / querying the memory
    # ------------------------------------------------------------------ #
    def get_file_summary(self, file_path: str) -> Optional[dict]:
        return self._data.get("files", {}).get(file_path)

    def list_all_files(self) -> list[str]:
        return sorted(self._data.get("files", {}).keys())

    def get_project_overview(self) -> dict:
        """
        A compact overview safe to hand to even a small/free LLM -
        this is the key trick: instead of dumping every file's full
        code, you dump this TINY summary (class/function names,
        table names) so it always fits in any model's context window.
        """
        files = self._data.get("files", {})
        overview = {
            "project_root": self._data.get("project_root"),
            "last_scanned_at": self._data.get("last_scanned_at"),
            "total_files": len(files),
            "modules": [],
        }
        for path, entry in sorted(files.items()):
            module_info = {
                "file": path,
                "type": entry.get("file_type"),
            }
            if entry.get("classes"):
                module_info["classes"] = [c["name"] for c in entry["classes"]]
            if entry.get("functions"):
                module_info["functions"] = [f["name"] for f in entry["functions"]]
            if entry.get("sql_tables"):
                module_info["tables"] = entry["sql_tables"]
            overview["modules"].append(module_info)
        return overview

    def search(self, keyword: str) -> list[dict]:
        """
        Simple, fast, offline keyword search across file names, class
        names, function names, and SQL table names. No AI needed for
        this - it's plain string matching, case-insensitive.
        """
        keyword_lower = keyword.lower()
        matches: list[dict] = []

        for path, entry in self._data.get("files", {}).items():
            hits = []

            if keyword_lower in path.lower():
                hits.append(("file_path", path))

            for cls in entry.get("classes", []):
                if keyword_lower in cls["name"].lower():
                    hits.append(("class", cls["name"]))
                for method in cls.get("methods", []):
                    if keyword_lower in method["name"].lower():
                        hits.append(("method", f"{cls['name']}.{method['name']}"))

            for func in entry.get("functions", []):
                if keyword_lower in func["name"].lower():
                    hits.append(("function", func["name"]))

            for table in entry.get("sql_tables", []):
                if keyword_lower in table.lower():
                    hits.append(("table", table))

            if hits:
                matches.append({"file": path, "matches": hits})

        return matches

    # ------------------------------------------------------------------ #
    # 🆕 CODE UNDERSTANDING ENHANCEMENTS
    # ------------------------------------------------------------------ #

    def get_import_graph(self) -> dict[str, list[str]]:
        """
        Cross-file import graph banata hai.
        Returns: {file_path: [imported_modules_that_are_local_files]}
        
        Example:
        {
            "ui/query_worker.py": ["memory_index.py", "llm_router.py"],
            "ui/main_window.py": ["ui/query_worker.py", "storage/chat_storage.py"],
        }
        """
        files = self._data.get("files", {})
        local_modules: dict[str, str] = {}  # module_name -> file_path
        
        # Pehle saare local modules ka naam map karo
        for path, entry in files.items():
            # "ui/query_worker.py" -> "ui.query_worker"
            module_name = path.replace("/", ".").replace("\\", ".").replace(".py", "")
            local_modules[module_name] = path
            # "query_worker" (bare name) bhi map karo
            bare_name = path.split("/")[-1].split("\\")[-1].replace(".py", "")
            local_modules[bare_name] = path
        
        # Ab har file ke imports check karo
        graph: dict[str, list[str]] = {}
        for path, entry in files.items():
            local_imports = []
            for imp in entry.get("imports", []):
                # "memory_index.MemoryIndex" -> "memory_index"
                base_module = imp.split(".")[0]
                # "ui.query_worker.QueryWorker" -> "ui.query_worker"
                parts = imp.split(".")
                for i in range(len(parts), 0, -1):
                    candidate = ".".join(parts[:i])
                    if candidate in local_modules:
                        target_file = local_modules[candidate]
                        if target_file != path and target_file not in local_imports:
                            local_imports.append(target_file)
                        break
                    # Bare name check
                    if parts[i-1] in local_modules:
                        target_file = local_modules[parts[i-1]]
                        if target_file != path and target_file not in local_imports:
                            local_imports.append(target_file)
                        break
            if local_imports:
                graph[path] = local_imports
        
        return graph

    def get_reverse_imports(self, target_file: str) -> list[str]:
        """
        Kaun si files target_file ko import karti hain?
        Example: get_reverse_imports("memory_index.py") 
                 -> ["ui/query_worker.py", "ui/scan_worker.py", "chroma_memory.py"]
        """
        graph = self.get_import_graph()
        target_normalized = target_file.replace("\\", "/").lower()
        
        importers = []
        for file_path, imports in graph.items():
            for imp in imports:
                if imp.replace("\\", "/").lower() == target_normalized:
                    importers.append(file_path)
                    break
        return importers

    def get_code_snippet(self, file_path: str, max_lines: int = 60) -> str | None:
        """
        File ka actual code read karta hai (limited lines).
        Chat context mein bhejne ke liye.
        """
        project_root = self._data.get("project_root")
        if not project_root:
            return None
        
        full_path = Path(project_root) / file_path
        if not full_path.exists():
            return None
        
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} more lines]"
            return content
        except Exception:
            return None

    def get_function_code(self, file_path: str, function_name: str) -> str | None:
        """
        Specific function ka actual code extract karta hai.
        Chat mein function-level understanding ke liye.
        """
        project_root = self._data.get("project_root")
        if not project_root:
            return None
        
        full_path = Path(project_root) / file_path
        if not full_path.exists():
            return None
        
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            
            # Function start dhundo
            start_idx = None
            indent_level = None
            for i, line in enumerate(lines):
                if f"def {function_name}(" in line or f"def {function_name} (" in line:
                    start_idx = i
                    indent_level = len(line) - len(line.lstrip())
                    break
            
            if start_idx is None:
                return None
            
            # Function end dhundo (next def/class at same or lower indent)
            end_idx = len(lines)
            for i in range(start_idx + 1, len(lines)):
                line = lines[i]
                if line.strip() == "":
                    continue
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and (
                    line.strip().startswith("def ") or 
                    line.strip().startswith("class ") or
                    (current_indent == 0 and line.strip() != "")
                ):
                    end_idx = i
                    break
            
            func_code = "\n".join(lines[start_idx:end_idx])
            # Limit to 80 lines max
            if end_idx - start_idx > 80:
                func_code = "\n".join(lines[start_idx:start_idx + 80]) + "\n... [truncated]"
            
            return func_code
        except Exception:
            return None
    
    def search_with_code(self, keyword: str, max_files: int = 3, max_lines_per_file: int = 40) -> str:
        """
        Enhanced search: keyword match + actual code snippets.
        Ye LLM ko bhejne ke liye ready-made context block return karta hai.
        """
        matches = self.search(keyword)
        if not matches:
            return ""
        
        lines = [f"📁 Matched files for '{keyword}' ({len(matches)} files):"]
        
        for match in matches[:max_files]:
            file_path = match["file"]
            match_details = ", ".join([f"{m[0]}: {m[1]}" for m in match["matches"][:3]])
            lines.append(f"\n### {file_path}")
            lines.append(f"   Matches: {match_details}")
            
            # Actual code snippet
            code = self.get_code_snippet(file_path, max_lines=max_lines_per_file)
            if code:
                lines.append(f"```python\n{code}\n```")
        
        return "\n".join(lines)


if __name__ == "__main__":
    import sys

    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    memory = MemoryIndex("erp_memory.json")

    print("Building/updating memory index...")
    report = memory.update_index_incremental(project_path)
    print(f"Added: {len(report['added'])}, Updated: {len(report['updated'])}, Removed: {len(report['removed'])}")

    print("\n--- Project Overview (this is what stays small and fits any model) ---")
    overview = memory.get_project_overview()
    print(f"Total files indexed: {overview['total_files']}")

    if len(sys.argv) > 2:
        keyword = sys.argv[2]
        print(f"\n--- Search results for '{keyword}' ---")
        for result in memory.search(keyword):
            print(result)
