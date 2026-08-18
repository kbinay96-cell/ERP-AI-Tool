# Updated: code_block_applier.py
from __future__ import annotations

import ast
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Union


@dataclass
class CodeBlock:
    """Full-file create/replace block: FILE: ... #start# ... #end#"""
    file_path: str
    content: str


@dataclass
class PatchBlock:
    """Find/replace patch block: FILE: ... #find# ... #replace# ... #end#

    find_text agar ek bare name hai (e.g. 'apply_all_blocks' ya
    'ClassName.method_name') to poora function/method AST se dhund kar
    replace hota hai. Warna find_text ko literal text maan kar exact
    match/replace hota hai.
    """
    file_path: str
    find_text: str
    replace_text: str


@dataclass
class ApplyResult:
    file_path: str
    success: bool
    message: str
    backup_path: Optional[str] = None


_BLOCK_PATTERN = re.compile(
    r"^\s*FILE\s*:\s*(?P<file>.+?)\s*\r?\n"
    r"(?:"
    r"^\s*#\s*start\s*#\s*\r?\n(?P<content>.*?)\r?\n?^\s*#\s*end\s*#"
    r"|"
    r"^\s*#\s*find\s*#\s*\r?\n(?P<find>.*?)\r?\n?^\s*#\s*replace\s*#\s*\r?\n(?P<replace>.*?)\r?\n?^\s*#\s*end\s*#"
    r")",
    re.DOTALL | re.IGNORECASE | re.MULTILINE,
)

# find_text ek FUNCTION/METHOD NAME maana jaata hai (literal code nahi)
# sirf tab jab wo ek bare identifier ho, optionally 'Class.method' style —
# koi code syntax (parens/colons/newlines) nahi. Ye sirf SHAPE check hai,
# koi keyword/language check nahi — isliye kisi bhi bhasha mein likha
# instruction ho, isse farak nahi padta.
_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")


def _is_function_name_pattern(text: str) -> bool:
    return bool(_NAME_PATTERN.match(text.strip()))


def parse_code_blocks(raw_text: str) -> list[Union[CodeBlock, PatchBlock]]:
    blocks: list[Union[CodeBlock, PatchBlock]] = []

    for match in _BLOCK_PATTERN.finditer(raw_text):
        file_path = match.group("file").strip()
        if not file_path:
            continue

        if match.group("content") is not None:
            blocks.append(CodeBlock(file_path=file_path, content=match.group("content")))
        else:
            blocks.append(
                PatchBlock(
                    file_path=file_path,
                    find_text=match.group("find"),
                    replace_text=match.group("replace"),
                )
            )

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
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_write_", dir=str(target_dir))
    os.close(fd)
    tmp_path_obj = Path(tmp_path)
    try:
        tmp_path_obj.write_text(content, encoding=encoding)
        os.replace(str(tmp_path_obj), str(target_path))
    finally:
        if tmp_path_obj.exists():
            try:
                tmp_path_obj.unlink()
            except Exception:
                pass


def _apply_full_block(project_root: str, block: CodeBlock) -> ApplyResult:
    full_path = (Path(project_root) / block.file_path).resolve()
    file_exists = full_path.is_file()

    backup_path = _make_backup(full_path, project_root) if file_exists else None
    _atomic_write_text(full_path, block.content, encoding="utf-8")

    action_label = "Updated" if file_exists else "Created"
    return ApplyResult(
        file_path=block.file_path,
        success=True,
        message=f"✅ {action_label}: {block.file_path}",
        backup_path=backup_path,
    )


def _find_function_nodes(tree: ast.Module, dotted_name: str) -> list:
    """'foo' -> koi bhi function/method jiska naam 'foo' ho.
    'Class.foo' -> sirf 'Class' ke andar wala method 'foo'."""
    parts = dotted_name.split(".")
    matches: list = []

    if len(parts) == 1:
        name = parts[0]
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                matches.append(node)

        if not matches:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
                            matches.append(child)

    elif len(parts) == 2:
        class_name, method_name = parts
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                        matches.append(child)

    return matches


def _apply_function_name_patch(
    project_root: str, full_path: Path, block: PatchBlock
) -> ApplyResult:
    original_text = full_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(original_text, filename=str(full_path))
    except SyntaxError as exc:
        return ApplyResult(
            file_path=block.file_path,
            success=False,
            message=f"❌ File mein pehle se hi syntax error hai, patch nahi kar sakte: {exc}",
        )

    matches = _find_function_nodes(tree, block.find_text.strip())

    if not matches:
        return ApplyResult(
            file_path=block.file_path,
            success=False,
            message=f"❌ Function/method '{block.find_text.strip()}' file mein nahi mila.",
        )

    if len(matches) > 1:
        return ApplyResult(
            file_path=block.file_path,
            success=False,
            message=(
                f"❌ '{block.find_text.strip()}' naam ke {len(matches)} functions/methods "
                f"mile — ambiguous hai. 'ClassName.{block.find_text.strip()}' format use karo."
            ),
        )

    node = matches[0]

    start_lineno = node.lineno
    if node.decorator_list:
        start_lineno = min(dec.lineno for dec in node.decorator_list)

    end_lineno = getattr(node, "end_lineno", None)
    if end_lineno is None:
        return ApplyResult(
            file_path=block.file_path,
            success=False,
            message="❌ Is Python version mein function ki end-line detect nahi ho payi.",
        )

    lines = original_text.splitlines(keepends=True)
    replace_text = block.replace_text
    if not replace_text.endswith("\n"):
        replace_text += "\n"

    new_lines = lines[: start_lineno - 1] + [replace_text] + lines[end_lineno:]
    new_text = "".join(new_lines)

    backup_path = _make_backup(full_path, project_root)
    _atomic_write_text(full_path, new_text, encoding="utf-8")

    return ApplyResult(
        file_path=block.file_path,
        success=True,
        message=f"✅ Function patched: {block.file_path} → {block.find_text.strip()}()",
        backup_path=backup_path,
    )


def _apply_literal_patch(project_root: str, full_path: Path, block: PatchBlock) -> ApplyResult:
    existing_text = full_path.read_text(encoding="utf-8")
    occurrence_count = existing_text.count(block.find_text)

    if occurrence_count == 0:
        return ApplyResult(
            file_path=block.file_path,
            success=False,
            message="❌ #find# wala text file mein nahi mila (exact match nahi hua). "
                    "Whitespace/indentation check karo.",
        )

    if occurrence_count > 1:
        return ApplyResult(
            file_path=block.file_path,
            success=False,
            message=f"❌ #find# wala text file mein {occurrence_count} baar mila — "
                    "ambiguous hai, safety ke liye apply nahi kiya.",
        )

    backup_path = _make_backup(full_path, project_root)
    new_text = existing_text.replace(block.find_text, block.replace_text, 1)
    _atomic_write_text(full_path, new_text, encoding="utf-8")

    return ApplyResult(
        file_path=block.file_path,
        success=True,
        message=f"✅ Patched: {block.file_path}",
        backup_path=backup_path,
    )


def _apply_patch_block(project_root: str, block: PatchBlock) -> ApplyResult:
    full_path = (Path(project_root) / block.file_path).resolve()

    if not full_path.is_file():
        return ApplyResult(
            file_path=block.file_path,
            success=False,
            message="❌ Patch ke liye file exist karni chahiye. Naya file banane "
                    "ke liye #start#/#end# use karo.",
        )

    if full_path.suffix.lower() == ".py" and _is_function_name_pattern(block.find_text):
        return _apply_function_name_patch(project_root, full_path, block)

    return _apply_literal_patch(project_root, full_path, block)


def apply_code_block(project_root: str, block: Union[CodeBlock, PatchBlock]) -> ApplyResult:
    try:
        if not _is_safe_path(project_root, block.file_path):
            return ApplyResult(
                file_path=block.file_path,
                success=False,
                message="❌ Rejected: file path project folder ke bahar jaata hai.",
            )

        if isinstance(block, PatchBlock):
            return _apply_patch_block(project_root, block)
        return _apply_full_block(project_root, block)

    except Exception as exc:
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
                message="❌ Koi valid code block nahi mila.",
            )
        ]

    return [apply_code_block(project_root, block) for block in blocks]


if __name__ == "__main__":
    print("code_block_applier.py loaded OK — teeno modes: full-file, "
          "function-name patch, literal patch.")