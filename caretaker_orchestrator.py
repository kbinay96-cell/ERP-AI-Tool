"""
caretaker_orchestrator.py

A minimal FastAPI single-window orchestrator that exposes endpoints to:
- accept pasted external code blocks and apply them (dry_run by default)
- run a pytest subset against the project

Security note: This is intended for local development and trusted networks only.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import subprocess
import os
import shlex

from code_block_applier import parse_code_blocks, apply_all_blocks

app = FastAPI(title="ERP-AI Caretaker Orchestrator")


class ApplyRequest(BaseModel):
    raw_text: str
    project_root: Optional[str] = "."
    dry_run: Optional[bool] = True


class ApplyResultItem(BaseModel):
    file_path: str
    success: bool
    message: str
    backup_path: Optional[str] = None


@app.post("/apply_code_blocks", response_model=List[ApplyResultItem])
def apply_code_blocks(req: ApplyRequest):
    # Validate project root
    root = os.path.abspath(req.project_root or ".")
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="project_root does not exist")

    blocks = parse_code_blocks(req.raw_text)
    if not blocks:
        raise HTTPException(status_code=400, detail="No code blocks parsed from input")

    if req.dry_run:
        # Return a simulated result listing parsed blocks without applying
        return [ApplyResultItem(file_path=b.file_path, success=False, message="DRY_RUN: would apply", backup_path=None) for b in blocks]

    # Apply blocks for real
    results = apply_all_blocks(root, req.raw_text)
    # Convert ApplyResult objects to serializable dicts
    output = []
    for r in results:
        output.append(ApplyResultItem(file_path=r.file_path, success=r.success, message=r.message, backup_path=r.backup_path))
    return output


class TestRequest(BaseModel):
    project_root: Optional[str] = "."
    pytest_args: Optional[str] = ""


@app.post("/run_tests")
def run_tests(req: TestRequest):
    root = os.path.abspath(req.project_root or ".")
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="project_root does not exist")

    args = f"pytest {req.pytest_args} -q"
    try:
        proc = subprocess.run(shlex.split(args), cwd=root, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="pytest timed out")

    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
