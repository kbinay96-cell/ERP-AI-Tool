import builtins
from types import SimpleNamespace

def test_build_index_calls(monkeypatch, tmp_path):
    # Minimal fake FileSummary
    fs = SimpleNamespace(file_path="foo.py", file_type="py", module_docstring="doc", classes=[], functions=[], sql_tables=[], line_count=10, file_hash="h1")
    # monkeypatch scan_project in chroma_memory to return our fake summary
    monkeypatch.setattr("chroma_memory.scan_project", lambda root: [fs])
    # fake chromadb collection API surface used by ChromaMemory
    fake_collection = SimpleNamespace(
        get=lambda: {"ids": [], "metadatas": []},
        add=lambda **kw: None,
        delete=lambda **kw: None,
        upsert=lambda **kw: None,
        query=lambda **kw: {"ids":[[]], "documents":[[]], "distances":[[]]}
    )
    # monkeypatch chromadb PersistentClient to return a client whose get_or_create_collection returns fake_collection
    monkeypatch.setitem(builtins.__dict__, "chromadb", SimpleNamespace(PersistentClient=lambda path: SimpleNamespace(get_or_create_collection=lambda name, embedding_function=None: fake_collection)))
    from chroma_memory import ChromaMemory
    mem = ChromaMemory(storage_dir=str(tmp_path))
    count = mem.build_full_index(str(tmp_path))
    assert count == 1