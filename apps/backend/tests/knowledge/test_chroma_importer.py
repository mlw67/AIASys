"""Chroma 原生磁盘存储导入器测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.knowledge.importers.chroma_importer import (
    ChromaImportError,
    _read_collection_from_queue,
    group_chroma_records_by_source,
    read_chroma_collection,
)


class TestGroupChromaRecordsBySource:
    def test_groups_by_source_metadata_key(self) -> None:
        ids = ["id-1", "id-2", "id-3"]
        documents = ["doc 1", "doc 2", "doc 3"]
        embeddings = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
        metadatas = [
            {"source": "file-a.txt"},
            {"source": "file-a.txt"},
            {"source": "file-b.txt"},
        ]

        groups = group_chroma_records_by_source(
            ids, documents, embeddings, metadatas, source_key="source"
        )

        assert set(groups.keys()) == {"file-a.txt", "file-b.txt"}
        assert len(groups["file-a.txt"]) == 2
        assert len(groups["file-b.txt"]) == 1
        assert groups["file-a.txt"][0]["chroma_id"] == "id-1"
        assert groups["file-b.txt"][0]["chroma_id"] == "id-3"

    def test_fallback_to_single_group_when_source_missing(self) -> None:
        ids = ["id-1"]
        documents = ["doc 1"]
        embeddings = [[1.0, 0.0]]
        metadatas = [{}]

        groups = group_chroma_records_by_source(
            ids, documents, embeddings, metadatas, source_key="source"
        )

        assert len(groups) == 1
        assert "__single__0" in groups
        assert groups["__single__0"][0]["content"] == "doc 1"

    def test_custom_source_key(self) -> None:
        ids = ["id-1", "id-2"]
        documents = ["doc 1", "doc 2"]
        embeddings = [[1.0, 0.0], [0.0, 1.0]]
        metadatas = [
            {"filename": "a.md"},
            {"filename": "b.md"},
        ]

        groups = group_chroma_records_by_source(
            ids, documents, embeddings, metadatas, source_key="filename"
        )

        assert set(groups.keys()) == {"a.md", "b.md"}


class TestReadChromaCollection:
    def test_raises_on_missing_directory(self) -> None:
        with pytest.raises(ChromaImportError, match="持久化目录不存在"):
            read_chroma_collection("/nonexistent/path", "test")

    def test_raises_on_invalid_directory(self, tmp_path: Path) -> None:
        with pytest.raises(ChromaImportError, match="未找到 chroma.sqlite3"):
            read_chroma_collection(str(tmp_path), "test")

    def test_reads_collection_with_embeddings(self, tmp_path: Path) -> None:
        chromadb = pytest.importorskip("chromadb")
        persist_dir = str(tmp_path / "chroma_data")
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.create_collection("test_collection")
        collection.add(
            ids=["id-1", "id-2"],
            documents=["hello world", "foo bar"],
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            metadatas=[{"source": "a.txt"}, {"source": "b.txt"}],
        )

        data = read_chroma_collection(persist_dir, "test_collection")

        assert set(data["ids"]) == {"id-1", "id-2"}
        assert set(data["documents"]) == {"hello world", "foo bar"}
        assert len(data["embeddings"]) == 2
        assert all(isinstance(emb, list) for emb in data["embeddings"])
        assert len(data["metadatas"]) == 2

    def test_reads_collection_from_queue_fallback(self, tmp_path: Path) -> None:
        chromadb = pytest.importorskip("chromadb")
        persist_dir = str(tmp_path / "chroma_data")
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.create_collection("fallback_collection")
        collection.add(
            ids=["id-1", "id-2"],
            documents=["hello world", "foo bar"],
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            metadatas=[{"source": "a.txt"}, {"source": "b.txt"}],
        )

        data = _read_collection_from_queue(persist_dir, "fallback_collection")

        assert set(data["ids"]) == {"id-1", "id-2"}
        assert set(data["documents"]) == {"hello world", "foo bar"}
        assert len(data["embeddings"]) == 2
        assert data["metadatas"] == [{"source": "a.txt"}, {"source": "b.txt"}]
