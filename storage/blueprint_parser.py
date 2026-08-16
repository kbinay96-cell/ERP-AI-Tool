"""
storage/blueprint_parser.py
Blueprint Parser - Any format -> Structured Blueprint
JSON direct parse karta hai, baaki formats AI se parse karwata hai.
User chahta hai: chahe tree ho ya flat, bas content samajhne layak ho.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Optional


def parse_blueprint_file(file_path: str) -> dict:
    """
    Main entry point.
    File path lo -> structured blueprint dict do.
    JSON ho to direct parse, baaki AI se parse.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        return _parse_json_direct(file_path)
    else:
        return _parse_with_ai(file_path)


def _parse_json_direct(file_path: str) -> dict:
    """JSON file ko direct parse karo aur normalize karo."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _normalize_blueprint(data, source_file=file_path)


def _parse_with_ai(file_path: str) -> dict:
    """
    Non-JSON file ko LLM se parse karwao.
    Option A: Seedha AI ko bhejo, confirm mat karo.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as exc:
        raise ValueError(f"File read failed: {exc}")

    # CSV file ho to pehle readable format mein convert karo
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        try:
            import csv
            import io
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
            if rows:
                headers = rows[0]
                table_lines = [" | ".join(headers)]
                table_lines.append("-" * 40)
                for row in rows[1:50]:  # Max 50 rows
                    table_lines.append(" | ".join(row))
                content = "\n".join(table_lines)
        except Exception:
            pass  # Raw content hi use karo

    # File bahut badi ho to truncate karo (LLM context limit)
    max_chars = 15000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n... [TRUNCATED]"

    from llm_router import ask_llm

    prompt = f"""You are a Blueprint Parser. Convert the following text into a structured JSON blueprint.

RULES:
1. Identify the blueprint title from the text.
2. Identify modules/sections if present.
3. For each task, extract:
   - "title": short task description
   - "expected_file": file path mentioned (or empty string if none)
   - "expected_function": function/class name mentioned (or empty string if none)
4. If no modules found, create a single module named "General".
5. Assign sequential IDs: module 1 tasks = T01, T02... module 2 = M02-T01, M02-T02...

OUTPUT FORMAT (STRICT JSON ONLY, no explanation):
{{
  "title": "Blueprint Title Here",
  "modules": [
    {{
      "name": "Module Name",
      "tasks": [
        {{
          "title": "Task description",
          "expected_file": "path/to/file.py",
          "expected_function": "function_name"
        }}
      ]
    }}
  ]
}}

TEXT TO PARSE:
{content}

JSON OUTPUT:"""

    response = ask_llm(prompt)

    # Response se JSON extract karo
    parsed = _extract_json_from_response(response)
    if parsed is None:
        raise ValueError(
            "AI se blueprint parse nahi ho paya. "
            "File ka format samajh nahi aaya. "
            "Kya ye blueprint ka content hai?"
        )

    return _normalize_blueprint(parsed, source_file=file_path)


def _extract_json_from_response(response: str) -> Optional[dict]:
    """LLM response se JSON object extract karo."""
    if not response:
        return None

    # Try 1: Direct JSON parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try 2: ```json ... ``` block se extract karo
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try 3: Pehle { aur last } ke beech ka text
    first_brace = response.find("{")
    last_brace = response.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(response[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None


def _normalize_blueprint(data: dict, source_file: str = "") -> dict:
    """
    Blueprint ko standard format mein convert karo
    jo blueprint_storage.py ke load_blueprint() ke saath compatible ho.
    """
    # Title extract karo
    title = data.get("title", "Untitled Blueprint")
    if not title:
        filename = os.path.basename(source_file) if source_file else "Unknown"
        title = f"Blueprint from {filename}"

    # Blueprint ID generate karo
    bp_id = data.get("blueprint_id", f"bp_{uuid.uuid4().hex[:8]}")

    # Tasks build karo (modules se ya direct tasks se)
    all_tasks = []
    modules = data.get("modules", [])

    if modules:
        # Module-wise tasks
        task_counter = 0
        for module in modules:
            module_name = module.get("name", "General")
            module_tasks = module.get("tasks", [])
            for task in module_tasks:
                task_counter += 1
                task_id = f"T{task_counter:03d}"
                all_tasks.append({
                    "id": task_id,
                    "title": task.get("title", "Untitled Task"),
                    "file": task.get("expected_file", ""),
                    "expected_function": task.get("expected_function", ""),
                    "module": module_name,
                    "status": "pending",
                    "completed_at": None,
                    "notes": "",
                })
    elif data.get("tasks"):
        # Direct tasks list (purana format compatible)
        for i, task in enumerate(data["tasks"], 1):
            all_tasks.append({
                "id": task.get("id", f"T{i:03d}"),
                "title": task.get("title", "Untitled Task"),
                "file": task.get("file", task.get("expected_file", "")),
                "expected_function": task.get("expected_function", ""),
                "module": task.get("module", "General"),
                "status": task.get("status", "pending"),
                "completed_at": task.get("completed_at"),
                "notes": task.get("notes", ""),
            })
    else:
        raise ValueError(
            "Blueprint mein koi tasks ya modules nahi mile. "
            "File ka content check karo."
        )

    # Final blueprint structure
    blueprint = {
        "blueprint_id": bp_id,
        "title": title,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "source_file": os.path.basename(source_file) if source_file else "",
        "status": "in_progress",
        "modules": modules,  # Original modules structure preserve karo
        "tasks": all_tasks,
        "progress": {
            "total_tasks": len(all_tasks),
            "done": sum(1 for t in all_tasks if t["status"] == "done"),
            "pending": sum(1 for t in all_tasks if t["status"] != "done"),
            "percentage": 0,
        },
    }

    # Percentage calculate karo
    total = blueprint["progress"]["total_tasks"]
    done = blueprint["progress"]["done"]
    blueprint["progress"]["percentage"] = round((done / total) * 100) if total > 0 else 0

    return blueprint


def get_supported_extensions() -> str:
    """Supported file extensions ka description (file dialog ke liye)."""
    return "All Files (*.json *.txt *.md *.yaml *.yml *.rst *.csv);;JSON (*.json);;Text (*.txt *.md *.yaml *.yml);;CSV (*.csv)"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python storage/blueprint_parser.py <file_path>")
        sys.exit(1)

    result = parse_blueprint_file(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))