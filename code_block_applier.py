# Updated: code_block_applier.py
from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# (existing dataclasses kept unchanged)
@dataclass
class CodeBlock:
    file_path: str
    action: str  # "replace" | "create"
    content: str


@dataclass
class ApplyResult:
    file_path: str
    success: bool
    message: str
    backup_path: Optional[str] = None


# Make the pattern resilient to both LF and CRLF line endings and to minor spacing.
# Anchor markers to line starts and use MULTILINE to avoid accidental mid-line matches.
_BLOCK_PATTERN = re.compile(
    r"^\s*###\s*FILE:\s*(?P<file>.+?)\s*\r?\n"
    r"^\s*###\s*ACTION:\s*(?P<action>replace|create)\s*\r?\n"
    r"^\s*<<<CODE_START>>>\s*\r?\n"
    r"(?P<content>.*?)"
    r"\r?\n?^\s*<<<CODE_END>>>",
    re.DOTALL | re.IGNORECASE | re.MULTILINE,
)


def parse_code_blocks(raw_text: str) -> list[CodeBlock]:
    blocks: list[CodeBlock] = []

    for match in _BLOCK_PATTERN.finditer(raw_text):
        file_path = match.group("file").strip()
        action = match.group("action").strip().lower()
        content = match.group("content")

        if not file_path:
            continue

        blocks.append(CodeBlock(file_path=file_path, action=action, content=content))

    return blocks


def _is_safe_path(project_root: str, relative_path: str) -> bool:
    root = Path(project_root).resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


def _make_backup(full_path: Path, project_root: str) -> Optional[str]:
    if not full_path.is_file():
        return None

    backup_root = Path(project_root) / "backups"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    relative = full_path.relative_to(Path(project_root).resolve())
    backup_path = backup_root / timestamp / relative

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(full_path, backup_path)

    return str(backup_path)


def _atomic_write_text(target_path: Path, content: str, encoding: str = "utf-8") -> None:
    """
    Write content to a temp file on the same filesystem, then atomically replace
    the target file with os.replace(). This avoids partial writes.
    """
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_write_", dir=str(target_dir))
    os.close(fd)
    tmp_path_obj = Path(tmp_path)
    try:
        tmp_path_obj.write_text(content, encoding=encoding)
        # Use os.replace for atomic rename (works across platforms)
        os.replace(str(tmp_path_obj), str(target_path))
    finally:
        # Ensure temp file doesn't remain if replace failed
        if tmp_path_obj.exists():
            try:
                tmp_path_obj.unlink()
            except Exception:
                pass


def apply_code_block(project_root: str, block: CodeBlock) -> ApplyResult:
    try:
        if not _is_safe_path(project_root, block.file_path):
            return ApplyResult(
                file_path=block.file_path,
                success=False,
                message="❌ Rejected: file path project folder ke bahar jaata hai.",
            )

        full_path = (Path(project_root) / block.file_path).resolve()
        file_exists = full_path.is_file()

        if block.action == "replace" and not file_exists:
            return ApplyResult(
                file_path=block.file_path,
                success=False,
                message="❌ ACTION=replace lekin file exist nahi karti. "
                        "Agar naya file hai to ACTION=create use karo.",
            )

        if block.action == "create" and file_exists:
            return ApplyResult(
                file_path=block.file_path,
                success=False,
                message="❌ ACTION=create lekin file already exist karti hai. "
                        "Agar overwrite karna hai to ACTION=replace use karo.",
            )

        # If replacing an existing file, make a timestamped backup first
        backup_path = _make_backup(full_path, project_root) if file_exists else None

        # Atomically write the new content
        _atomic_write_text(full_path, block.content, encoding="utf-8")

        action_label = "Updated" if file_exists else "Created"
        return ApplyResult(
            file_path=block.file_path,
            success=True,
            message=f"✅ {action_label}: {block.file_path}",
            backup_path=backup_path,
        )

    except Exception as exc:  # never crash caller
        return ApplyResult(
            file_path=block.file_path,
            success=False,
            message=f"❌ Failed: {exc}",
        )


def apply_all_blocks(project_root: str, raw_text: str) -> list[ApplyResult]:
    blocks = parse_code_blocks(raw_text)

    if not blocks:
        return [
            ApplyResult(
                file_path="(none)",
                success=False,
                message="❌ Koi valid code block nahi mila. Format check karo: "
                        "### FILE: ... / ### ACTION: ... / <<<CODE_START>>> ... <<<CODE_END>>>",
            )
        ]

    return [apply_code_block(project_root, block) for block in blocks]


if __name__ == "__main__":
    sample = """
 ### FILE: test_output/sample.py
 ### ACTION: create
 <<<CODE_START>>>
 print("hello from applied code block")
 <<<CODE_END>>>
 """
    results = apply_all_blocks(".", sample)
    for r in results:
        print(r.message)
