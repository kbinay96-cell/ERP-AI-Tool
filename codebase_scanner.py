"""
codebase_scanner.py

Codebase Reader - Medical ERP AI Tool
---------------------------------------------------------
Purpose:
    Scans a project folder and extracts a structured summary
    of every source file (classes, functions, docstrings,
    SQL tables) WITHOUT sending anything to any API.

    This is pure Python (uses the built-in `ast` module for
    .py files), so it works 100% offline, with zero external
    dependencies and zero cost.

    This module NEVER modifies any file - it only reads.
"""

from __future__ import annotations

import ast
import os
import re
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# File types this scanner understands. Add more extensions here
# as your project grows (e.g. ".js", ".html") - each needs its
# own small parser function below.
SUPPORTED_EXTENSIONS = {".py", ".sql", ".ui"}

# Folders to skip entirely - virtual envs, git internals, caches.
IGNORED_DIR_NAMES = {
    ".git", "__pycache__", "venv", "env",
    "node_modules", "logs",
    "site-packages", "dist-packages",
    "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}


def _should_ignore_dir(name: str) -> bool:
    """Har dot-folder (.venv, .venv-openhands, .idea, .vscode, .git, etc.)
    aur koi bhi 'venv' wala naam (case-insensitive) generically skip karta
    hai - sirf exact-match list par depend nahi karta."""
    if name.startswith("."):
        return True
    if "venv" in name.lower():
        return True
    if name.endswith(".egg-info"):
        return True
    return name in IGNORED_DIR_NAMES


@dataclass
class FunctionSummary:
    name: str
    args: list[str]
    docstring: Optional[str]
    line_number: int


@dataclass
class ClassSummary:
    name: str
    docstring: Optional[str]
    methods: list[FunctionSummary]
    line_number: int


@dataclass
class FileSummary:
    file_path: str            # relative path from project root
    file_type: str            # "python" | "sql" | "ui"
    line_count: int
    file_hash: str            # used to detect changes on rescan
    module_docstring: Optional[str] = None
    classes: list[ClassSummary] = field(default_factory=list)
    functions: list[FunctionSummary] = field(default_factory=list)
    sql_tables: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    error: Optional[str] = None  # set if the file couldn't be parsed

    def to_dict(self) -> dict:
        return asdict(self)


def _file_hash(content: str) -> str:
    """Short hash used to detect whether a file changed since last scan."""
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _parse_python_file(path: Path, relative_path: str) -> FileSummary:
    """
    Parses a .py file using Python's built-in `ast` module.
    This is NOT an AI operation - `ast` is Python's own compiler
    front-end, so this is 100% deterministic and offline.
    """
    content = path.read_text(encoding="utf-8", errors="ignore")
    summary = FileSummary(
        file_path=relative_path,
        file_type="python",
        line_count=content.count("\n") + 1,
        file_hash=_file_hash(content),
    )

    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError as exc:
        summary.error = f"SyntaxError while parsing: {exc}"
        return summary

    summary.module_docstring = ast.get_docstring(tree)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            summary.imports.extend(_extract_import_names(node))

        elif isinstance(node, ast.ClassDef):
            methods = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(_summarize_function(child))
            summary.classes.append(
                ClassSummary(
                    name=node.name,
                    docstring=ast.get_docstring(node),
                    methods=methods,
                    line_number=node.lineno,
                )
            )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            summary.functions.append(_summarize_function(node))

    return summary


def _summarize_function(node) -> FunctionSummary:
    args = [a.arg for a in node.args.args]
    return FunctionSummary(
        name=node.name,
        args=args,
        docstring=ast.get_docstring(node),
        line_number=node.lineno,
    )


def _extract_import_names(node) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return [f"{module}.{alias.name}" for alias in node.names]
    return []


_SQL_TABLE_PATTERN = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)",
    re.IGNORECASE,
)


def _parse_sql_file(path: Path, relative_path: str) -> FileSummary:
    """Extracts table names from a .sql file via regex - no SQL execution happens."""
    content = path.read_text(encoding="utf-8", errors="ignore")
    tables = _SQL_TABLE_PATTERN.findall(content)
    return FileSummary(
        file_path=relative_path,
        file_type="sql",
        line_count=content.count("\n") + 1,
        file_hash=_file_hash(content),
        sql_tables=sorted(set(tables)),
    )


def _parse_ui_file(path: Path, relative_path: str) -> FileSummary:
    """
    .ui files are XML (Qt Designer). We don't need a full XML parse for
    a summary - just capture size/hash so changes are detected, plus a
    quick widget-class count via regex (informational only).
    """
    content = path.read_text(encoding="utf-8", errors="ignore")
    widget_classes = re.findall(r'class="([A-Za-z0-9_]+)"', content)
    summary = FileSummary(
        file_path=relative_path,
        file_type="ui",
        line_count=content.count("\n") + 1,
        file_hash=_file_hash(content),
    )
    # Reuse sql_tables list field to store widget class counts info-free;
    # cleaner: store in imports field as a lightweight info carrier.
    if widget_classes:
        top_widgets = sorted(set(widget_classes))
        summary.imports = top_widgets[:20]  # cap to keep summary small
    return summary


def scan_file(path: Path, project_root: Path) -> Optional[FileSummary]:
    """Dispatches to the correct parser based on file extension."""
    relative_path = str(path.relative_to(project_root)).replace("\\", "/")
    suffix = path.suffix.lower()

    try:
        if suffix == ".py":
            return _parse_python_file(path, relative_path)
        if suffix == ".sql":
            return _parse_sql_file(path, relative_path)
        if suffix == ".ui":
            return _parse_ui_file(path, relative_path)
    except Exception as exc:  # noqa: BLE001 - a bad file must never crash the whole scan
        return FileSummary(
            file_path=relative_path,
            file_type=suffix.lstrip("."),
            line_count=0,
            file_hash="",
            error=f"Could not read file: {exc}",
        )

    return None


def scan_project(project_root: str) -> list[FileSummary]:
    """
    Walks the entire project folder and returns a list of FileSummary
    objects - one per recognized source file. This is the main entry
    point of the Codebase Reader.
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Project path does not exist or is not a folder: {root}")

    summaries: list[FileSummary] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_ignore_dir(d)]

        for filename in filenames:
            file_path = Path(dirpath) / filename
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            result = scan_file(file_path, root)
            if result is not None:
                summaries.append(result)

    return summaries


if __name__ == "__main__":
    import sys
    import json

    target = sys.argv[1] if len(sys.argv) > 1 else "."
    results = scan_project(target)
    print(f"Scanned {len(results)} files.")
    print(json.dumps([r.to_dict() for r in results[:3]], indent=2))
