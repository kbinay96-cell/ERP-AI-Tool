"""
storage/blueprint_storage.py

Blueprint Storage - ERP-AI-Tool
Blueprint ko load, track, compare, aur archive karta hai.
"""

import json
import os
from datetime import datetime
from typing import Optional

BLUEPRINT_DIR = "blueprints"
ARCHIVE_DIR = os.path.join(BLUEPRINT_DIR, "archive")
ACTIVE_FILE = os.path.join(BLUEPRINT_DIR, "active_blueprint.json")


def _ensure_dirs() -> None:
    """Blueprint directories create karo agar nahi hain."""
    os.makedirs(BLUEPRINT_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def load_blueprint(blueprint_data: dict) -> bool:
    """
    Naya blueprint load karo.
    Agar pehle se koi active blueprint hai to archive mein chala jayega.
    """
    _ensure_dirs()

    # Pehle se active blueprint hai to archive karo
    if os.path.exists(ACTIVE_FILE):
        archive_current()

    blueprint_data["loaded_at"] = datetime.now().isoformat()
    blueprint_data["status"] = "in_progress"

    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(blueprint_data, f, ensure_ascii=False, indent=2)

    return True


def get_active_blueprint() -> Optional[dict]:
    """Currently loaded blueprint return karo."""
    if not os.path.exists(ACTIVE_FILE):
        return None

    with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def update_task_status(task_id: str, status: str, notes: str = "") -> bool:
    """
    Kisi task ka status update karo.
    status: "pending" | "in_progress" | "done" | "blocked"
    """
    blueprint = get_active_blueprint()
    if not blueprint:
        return False

    for task in blueprint["tasks"]:
        if task["id"] == task_id:
            task["status"] = status
            task["notes"] = notes
            if status == "done":
                task["completed_at"] = datetime.now().isoformat()
            else:
                task["completed_at"] = None
            break
    else:
        return False

    # Progress recalculate karo
    _recalculate_progress(blueprint)

    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(blueprint, f, ensure_ascii=False, indent=2)

    return True


def mark_task_done_by_file(file_path: str, notes: str = "") -> bool:
    """
    File path se task dhund ke done mark karo.
    Agent jab file create/edit kare to ye call hoga.
    """
    blueprint = get_active_blueprint()
    if not blueprint:
        return False

    # Normalize path for comparison
    normalized = file_path.replace("\\", "/").lower()

    for task in blueprint["tasks"]:
        task_file = task.get("file", "").replace("\\", "/").lower()
        if task_file in normalized or normalized in task_file:
            task["status"] = "done"
            task["completed_at"] = datetime.now().isoformat()
            task["notes"] = notes
            break
    else:
        return False

    _recalculate_progress(blueprint)

    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(blueprint, f, ensure_ascii=False, indent=2)

    return True
def _recalculate_progress(blueprint: dict) -> None:
    """Blueprint ka progress counter recalculate karo."""
    total = len(blueprint.get("tasks", []))
    done = sum(1 for t in blueprint.get("tasks", []) if t.get("status") == "done")
    pending = total - done
    percentage = round((done / total) * 100) if total > 0 else 0
    blueprint["progress"] = {
        "total_tasks": total,
        "done": done,
        "pending": pending,
        "percentage": percentage,
    }

def get_progress_report() -> str:
    """
    Human-readable progress report return karo.
    Agent ye report user ko dikhayega.
    """
    blueprint = get_active_blueprint()
    if not blueprint:
        return "Koi active blueprint loaded nahi hai."

    p = blueprint["progress"]
    title = blueprint["title"]

    lines = [
        f"📋 Blueprint: {title}",
        f"📊 Progress: {p['done']}/{p['total_tasks']} tasks done ({p['percentage']}%)",
        "",
        "✅ DONE:",
    ]

    for task in blueprint["tasks"]:
        if task["status"] == "done":
            lines.append(f"   ✅ {task['id']}: {task['title']} ({task['file']})")

    lines.append("")
    lines.append("⏳ PENDING:")

    for task in blueprint["tasks"]:
        if task["status"] != "done":
            status_icon = {"pending": "⬜", "in_progress": "🔄", "blocked": "🚫"}
            icon = status_icon.get(task["status"], "⬜")
            lines.append(f"   {icon} {task['id']}: {task['title']} ({task['file']})")

    return "\n".join(lines)


def compare_with_repo(project_root: str) -> str:
    """
    Blueprint tasks ko actual repo files se compare karo.
    Agent ye use karega ye check karne ke liye ki
    kaunsi files actually exist karti hain.
    """
    blueprint = get_active_blueprint()
    if not blueprint:
        return "Koi active blueprint loaded nahi hai."

    lines = [f"🔍 Repo Comparison: {blueprint['title']}", ""]

    for task in blueprint["tasks"]:
        file_path = os.path.join(project_root, task.get("file", ""))
        exists = os.path.isfile(file_path)

        if exists and task["status"] != "done":
            lines.append(
                f"⚠️  {task['id']}: File EXISTS but task marked '{task['status']}'"
                f"\n   → {task['file']}"
                f"\n   → Suggestion: Task ko 'done' mark karo"
            )
        elif not exists and task["status"] == "done":
            lines.append(
                f"❌ {task['id']}: Task marked 'done' but FILE MISSING!"
                f"\n   → {task['file']}"
                f"\n   → Action: File banao ya task reset karo"
            )
        elif exists and task["status"] == "done":
            lines.append(f"✅ {task['id']}: {task['file']} — OK")
        else:
            lines.append(f"⬜ {task['id']}: {task['file']} — Pending")

    return "\n".join(lines)


def archive_current() -> None:
    """Current active blueprint ko archive mein move karo."""
    if not os.path.exists(ACTIVE_FILE):
        return

    with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
        blueprint = json.load(f)

    bp_id = blueprint.get("blueprint_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(ARCHIVE_DIR, f"{bp_id}_{timestamp}.json")

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(blueprint, f, ensure_ascii=False, indent=2)

    os.remove(ACTIVE_FILE)


def remove_active_blueprint() -> None:
    """Active blueprint delete karo (archive ke bina)."""
    if os.path.exists(ACTIVE_FILE):
        os.remove(ACTIVE_FILE)