"""
chroma_memory.py

Local ChromaDB semantic memory layer. Defensive access changes made to avoid
KeyError when collection.get() returns unexpected shapes in different chromadb
versions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from codebase_scanner import FileSummary, scan_project


def _build_text_chunk(summary: FileSummary) -> str:
    """
    Converts one file's structured summary into a short natural-language
    description - this text is what gets embedded, so it should read
    like a plain-English summary of what the file does.
    """
    parts = [f"File: {summary.file_path} (type: {summary.file_type})"]

    if summary.module_docstring:
        parts.append(f"Description: {summary.module_docstring.strip()[:300]}")

    if summary.classes:
        class_lines = []
        for cls in summary.classes:
            method_names = ", ".join(m.name for m in cls.methods[:10])
            class_lines.append(f"class {cls.name} (methods: {method_names})")
        parts.append("Classes: " + " | ".join(class_lines))

    if summary.functions:
        func_names = ", ".join(f.name for f in summary.functions[:15])
        parts.append(f"Functions: {func_names}")

    if summary.sql_tables:
        parts.append(f"Database tables defined: {', '.join(summary.sql_tables)}")

    return "\n".join(parts)


class ChromaMemory:
    """Manages a local, persistent ChromaDB collection for one project."""

    def __init__(self, storage_dir: str = "./erp_chroma_memory", collection_name: str = "erp_codebase") -> None:
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError as exc:
            raise ImportError(
                "chromadb and sentence-transformers are required for this module.\n"
                "Install with: pip install chromadb sentence-transformers"
            ) from exc

        Path(storage_dir).mkdir(parents=True, exist_ok=True)

        # PersistentClient stores everything in `storage_dir` on disk -
        # no server, no network call, no account needed.
        self._client = chromadb.PersistentClient(path=storage_dir)

        # This embedding model downloads once from Hugging Face the
        # first time it's used, then is cached locally and works
        # fully offline on every subsequent run.
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
        )

    def build_full_index(self, project_root: str) -> int:
        """Scans the project and (re)builds the semantic index from scratch."""
        summaries = scan_project(project_root)

        # Clear existing entries for a clean rebuild.
        existing = self._collection.get() or {}
        existing_ids = existing.get("ids", [])
        if existing_ids:
            self._collection.delete(ids=existing_ids)

        documents, ids, metadatas = [], [], []
        for summary in summaries:
            documents.append(_build_text_chunk(summary))
            ids.append(summary.file_path)
            metadatas.append({
                "file_type": summary.file_type,
                "line_count": summary.line_count,
                "file_hash": summary.file_hash,
            })

        if documents:
            self._collection.add(documents=documents, ids=ids, metadatas=metadatas)

        return len(documents)

    def update_index_incremental(self, project_root: str) -> dict:
        """Only re-embeds files that changed since the last index build."""
        # inside update_index_incremental(...)
        summaries = scan_project(project_root)
        existing = self._collection.get() or {}
        existing_ids = existing.get("ids", [])
        existing_metas = existing.get("metadatas", [])

        existing_hashes = {
            file_id: meta.get("file_hash") if isinstance(meta, dict) else None
            for file_id, meta in zip(existing_ids, existing_metas)
        }

        to_upsert_docs, to_upsert_ids, to_upsert_meta = [], [], []
        current_ids = set()

        for summary in summaries:
            current_ids.add(summary.file_path)
            if existing_hashes.get(summary.file_path) == summary.file_hash:
                continue  # unchanged - skip re-embedding to save time
            to_upsert_docs.append(_build_text_chunk(summary))
            to_upsert_ids.append(summary.file_path)
            to_upsert_meta.append({
                "file_type": summary.file_type,
                "line_count": summary.line_count,
                "file_hash": summary.file_hash,
            })

        if to_upsert_ids:
            self._collection.upsert(
                documents=to_upsert_docs, ids=to_upsert_ids, metadatas=to_upsert_meta
            )

        removed_ids = [fid for fid in existing.get("ids", []) if fid not in current_ids]
        if removed_ids:
            self._collection.delete(ids=removed_ids)

        return {
            "changed_or_new": len(to_upsert_ids),
            "removed": len(removed_ids),
            "unchanged": len(summaries) - len(to_upsert_ids),
        }

    def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Searches by MEANING, not exact keyword. E.g. query
        "where is password hashing done" will surface
        engines/password_manager.py even without those exact words.
        """
        results = self._collection.query(query_texts=[query], n_results=top_k)

        output = []
        for i in range(len(results.get("ids", [[]])[0])):
            output.append({
                "file": results.get("ids", [[]])[0][i],
                "relevance_score": results.get("distances", [[]])[0][i] if results.get("distances") else None,
                "summary": results.get("documents", [[]])[0][i],
            })
        return output


if __name__ == "__main__":
    import sys

    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    memory = ChromaMemory(storage_dir="./erp_chroma_memory")

    print("Building semantic index (first run downloads the embedding model once)...")
    count = memory.build_full_index(project_path)
    print(f"Indexed {count} files.")

    if len(sys.argv) > 2:
        query = sys.argv[2]
        print(f"\n--- Semantic search results for: '{query}' ---")
        for result in memory.semantic_search(query):
            print(f"\nFile: {result['file']} (score: {result['relevance_score']})")
            print(result["summary"][:200])
