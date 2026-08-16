"""
caretaker_orchestrator.py

FastAPI single-window orchestrator for the Medical ERP v2 caretaker.

Endpoints:
- POST /preview_code_blocks
- POST /apply_and_run_sandbox

Security: intended for local/trusted usage only.
"""
from __future__ import annotations

import difflib
import os
import shlex
import subprocess
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from code_block_applier import parse_code_blocks, apply_all_blocks

app = FastAPI(title="ERP-AI Caretaker Orchestrator (Medical ERP v2)")


class RawRequest(BaseModel):
    raw_text: str
    project_root: Optional[str] = "."


class PreviewItem(BaseModel):
    file_path: str
    diff: str


@app.post("/preview_code_blocks", response_model=List[PreviewItem])
def preview_code_blocks(req: RawRequest):
    root = Path(req.project_root or ".").resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail="project_root does not exist")

    blocks = parse_code_blocks(req.raw_text)
    if not blocks:
        raise HTTPException(status_code=400, detail="No code blocks parsed from input")

    previews: List[PreviewItem] = []
    for b in blocks:
        target = (root / b.file_path).resolve()
        try:
            target.relative_to(root)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid target path: {b.file_path}")

        existing_text = ""
        if target.exists():
            existing_text = target.read_text(encoding="utf-8")
        new_text = b.content

        diff_lines = difflib.unified_diff(
            existing_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(target),
            tofile=str(target),
            lineterm="",
        )
        diff_str = "".join(diff_lines)
        previews.append(PreviewItem(file_path=b.file_path, diff=diff_str))

    return previews


class ApplyAndRunRequest(BaseModel):
    raw_text: str
    project_root: Optional[str] = "."
    pytest_args: Optional[str] = ""


def _to_dict(obj):
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "__dict__"):
        return vars(obj)
    if isinstance(obj, dict):
        return obj
    return str(obj)


@app.post("/apply_and_run_sandbox")
def apply_and_run_sandbox(req: ApplyAndRunRequest):
    root = Path(req.project_root or ".").resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail="project_root does not exist")

    apply_results = apply_all_blocks(str(root), req.raw_text)

    pytest_args = (req.pytest_args or "").strip()
    if pytest_args:
        cmd = f"pytest {pytest_args} -q"
    else:
        return {"apply_results": [_to_dict(r) for r in apply_results], "pytest": None}

    try:
        proc = subprocess.run(
            shlex.split(cmd), cwd=str(root), capture_output=True, text=True, timeout=300
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="pytest timed out")

    return {
        "apply_results": [_to_dict(r) for r in apply_results],
        "pytest": {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        },
    }
