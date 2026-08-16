"""
tools/repo_reader.py

Repository Reader - ERP-AI-Tool
Agent ko repo files padhne, search karne, aur samajhne mein madad karta hai.
"""

import os
import re
from typing import Optional


def read_file(file_path: str, max_lines: int = 200) -> str:
    """
    File ka content return karo.
    max_lines se zyada nahi padhega (context overflow se bachne ke liye).
    """
    if not os.path.isfile(file_path):
        return f"❌ File not found: {file_path}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)

        if total_lines > max_lines:
            content = "".join(lines[:max_lines])
            content += f"\n... [{total_lines - max_lines} more lines truncated]"
        else:
            content = "".join(lines)

        header = f"📄 File: {file_path} ({total_lines} lines)\n"
        header += "=" * 60 + "\n"
        return header + content

    except Exception as exc:
        return f"❌ Error reading file: {exc}"


def search_in_file(file_path: str, pattern: str) -> str:
    """
    File mein specific pattern search karo.
    Function name, class name, variable name — kuch bhi.
    """
    if not os.path.isfile(file_path):
        return f"❌ File not found: {file_path}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        matches = []
        pattern_lower = pattern.lower()

        for i, line in enumerate(lines, 1):
            if pattern_lower in line.lower():
                matches.append(f"  Line {i}: {line.rstrip()}")

        if not matches:
            return f"'{pattern}' not found in {file_path}"

        header = f"🔍 '{pattern}' in {file_path} ({len(matches)} matches):\n"
        return header + "\n".join(matches[:20])  # Max 20 matches

    except Exception as exc:
        return f"❌ Error searching: {exc}"


def extract_function(file_path: str, function_name: str) -> str:
    """
    File se specific function ka code extract karo. Uses AST for robust extraction.
    """
    if not os.path.isfile(file_path):
        return f"❌ File not found: {file_path}"

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Parse AST to find the function or class with that name
        import ast

        tree = ast.parse(content)
        target_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == function_name:
                    target_node = node
                    break

        if target_node is None:
            return f"❌ Function/Class '{function_name}' not found in {file_path}"

        # Determine start and end line numbers
        start_lineno = getattr(target_node, "lineno", None)
        end_lineno = getattr(target_node, "end_lineno", None)

        lines = content.splitlines()

        if start_lineno is None:
            return f"❌ Could not determine location of '{function_name}'"

        if end_lineno is None:
            # Fallback: scan forward until next top-level def/class at same indent
            indent = len(lines[start_lineno - 1]) - len(lines[start_lineno - 1].lstrip())
            end_idx = len(lines)
            for i in range(start_lineno, len(lines)):
                line = lines[i]
                if line.strip() == "":
                    continue
                current_indent = len(line) - len(line.lstrip())
                stripped = line.lstrip()
                if current_indent <= indent and (stripped.startswith("def ") or stripped.startswith("class ")):
                    end_idx = i
                    break
            end_lineno = end_idx

        # Slice the content
        func_code = "\n".join(lines[start_lineno - 1:end_lineno])
        header = f"🔧 Function/Class '{function_name}' in {file_path}:\n"
        header += "=" * 60 + "\n"
        return header + func_code

    except Exception as exc:
        return f"❌ Error extracting function: {exc}"


def list_directory(dir_path: str, max_depth: int = 2) -> str:
    """
    Directory ka tree structure return karo.
    """
    if not os.path.isdir(dir_path):
        return f"❌ Directory not found: {dir_path}"

    lines = [f"📁 {dir_path}/"]

    for root, dirs, files in os.walk(dir_path):
        # Calculate depth
        depth = root.replace(dir_path, "").count(os.sep)
        if depth >= max_depth:
            dirs.clear()
            continue

        # Skip hidden and common ignore dirs
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in {
                "__pycache__", "node_modules", ".venv", "venv", ".git"
            }
        ]

        indent = "  " * (depth + 1)

        for d in sorted(dirs):
            lines.append(f"{indent}📂 {d}/")

        for f in sorted(files):
            if not f.startswith("."):
                lines.append(f"{indent}📄 {f}")

    return "\n".join(lines)


def web_search_instruction() -> str:
    """
    Web search ke liye agent ko instruction return karo.
    Agent terminal tool se curl/wget use karke search kar sakta hai.
    """
    return (
        "🌐 Web Search Available.\n"
        "Agent can use terminal to search:\n"
        "  - curl for API calls\n"
        "  - Python requests for web scraping\n"
        "  - DuckDuckGo HTML search (no API key needed)\n\n"
        "Example:\n"
        "  python -c \"import urllib.request; "
        "print(urllib.request.urlopen("
        "'https://html.duckduckgo.com/html/?q=postgresql+partial+index'"
        ").read().decode()[:2000])\"\n"
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python tools/repo_reader.py <command> <path> [extra]")
        print("Commands: read, search, extract, list")
        sys.exit(1)

    cmd = sys.argv[1]
    path = sys.argv[2]

    if cmd == "read":
        print(read_file(path))
    elif cmd == "search":
        if len(sys.argv) < 4:
            print("Missing pattern for search")
            sys.exit(1)
        print(search_in_file(path, sys.argv[3]))
    elif cmd == "extract":
        if len(sys.argv) < 4:
            print("Missing function name for extract")
            sys.exit(1)
        print(extract_function(path, sys.argv[3]))
    elif cmd == "list":
        print(list_directory(path))
    else:
        print(f"Unknown command: {cmd}")