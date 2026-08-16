import os
from fastapi.testclient import TestClient
from types import SimpleNamespace

import caretaker_orchestrator as co

client = TestClient(co.app)


def test_preview_code_blocks(tmp_path):
    sample = """### FILE: hello/world.txt
### ACTION: create
<<<CODE_START>>>
hello from preview
<<<CODE_END>>>
"""
    resp = client.post("/preview_code_blocks", json={"raw_text": sample, "project_root": str(tmp_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert "+++" in data[0]["diff"] or "@@" in data[0]["diff"]


def test_apply_and_run_sandbox_monkeypatched(monkeypatch, tmp_path):
    fake_result = SimpleNamespace(file_path="a.py", success=True, message="ok", backup_path=None)
    monkeypatch.setattr(co, "apply_all_blocks", lambda root, raw_text: [fake_result])

    class FakeProc:
        def __init__(self):
            self.returncode = 0
            self.stdout = "pytests ran"
            self.stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: FakeProc())

    sample = """### FILE: a.py
### ACTION: replace
<<<CODE_START>>>
print("ok")
<<<CODE_END>>>
"""
    resp = client.post("/apply_and_run_sandbox", json={"raw_text": sample, "project_root": str(tmp_path), "pytest_args": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert "apply_results" in data
    assert data["pytest"] is None
