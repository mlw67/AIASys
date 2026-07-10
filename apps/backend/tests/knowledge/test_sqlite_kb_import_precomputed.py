"""SQLiteKBService.import_precomputed_chunks 导入预计算向量测试。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.knowledge.models import KnowledgeBaseCreate
from app.knowledge.sqlite_kb_service import SQLiteKBService


class _ModelConfigStub:
    model_type = "embedding"
    dimension = 4
    model = "test-embedding"


def _stub_llm_config_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """用固定维度返回的 stub 替换 LLM 配置服务。"""
    monkeypatch.setattr("app.core.config.WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(
        "app.knowledge.sqlite_kb_service.get_llm_config_service",
        lambda: type(
            "LLMConfigStub",
            (),
            {
                "resolve_default_embedding_model_id": lambda self, user_id: "test-embedding",
                "resolve_embedding_model_config": lambda self, user_id, model_id: {
                    "model_name": model_id,
                    "dimension": 4,
                },
                "get_model": lambda self, user_id, model_id: _ModelConfigStub(),
            },
        )(),
    )


class TestImportPrecomputedChunks:
    async def test_imports_chunks_and_vectors_without_embedding_api(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_llm_config_service(monkeypatch, tmp_path)

        service = SQLiteKBService()
        kb = service.create_knowledge_base(
            "local_default",
            KnowledgeBaseCreate(name="import-test"),
        )

        chunks = [
            {
                "index": 0,
                "content": "hello world",
                "metadata": {"source": "a.txt", "chroma_id": "c-1"},
            },
            {
                "index": 1,
                "content": "foo bar",
                "metadata": {"source": "a.txt", "chroma_id": "c-2"},
            },
        ]
        embeddings = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ]

        result = await service.import_precomputed_chunks(
            user_id="local_default",
            kb_id=kb.id,
            filename="a.txt",
            chunks=chunks,
            embeddings=embeddings,
            embedding_model="test-embedding",
        )

        assert result.success is True
        assert result.chunk_count == 2
        assert result.embedding_model == "test-embedding"

        # 验证数据库内容
        db_path = service._find_db_file("local_default", kb.id)
        assert db_path is not None
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT chunk_id, content FROM kb_chunks ORDER BY chunk_index"
            ).fetchall()
            assert len(rows) == 2
            assert rows[0][1] == "hello world"
            assert rows[1][1] == "foo bar"

            doc_row = conn.execute("SELECT status, chunk_count FROM kb_documents").fetchone()
            assert doc_row == ("completed", 2)
        finally:
            conn.close()

    async def test_rejects_dimension_mismatch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_llm_config_service(monkeypatch, tmp_path)

        service = SQLiteKBService()
        kb = service.create_knowledge_base(
            "local_default",
            KnowledgeBaseCreate(name="import-test"),
        )

        chunks = [{"index": 0, "content": "x", "metadata": {}}]
        embeddings = [[1.0, 0.0]]  # 2 维，与配置 4 维不一致

        with pytest.raises(ValueError, match="向量维度"):
            await service.import_precomputed_chunks(
                user_id="local_default",
                kb_id=kb.id,
                filename="x.txt",
                chunks=chunks,
                embeddings=embeddings,
                embedding_model="test-embedding",
            )

    async def test_rejects_length_mismatch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_llm_config_service(monkeypatch, tmp_path)

        service = SQLiteKBService()
        kb = service.create_knowledge_base(
            "local_default",
            KnowledgeBaseCreate(name="import-test"),
        )

        chunks = [{"index": 0, "content": "x", "metadata": {}}]
        embeddings = []

        with pytest.raises(ValueError, match="长度不一致"):
            await service.import_precomputed_chunks(
                user_id="local_default",
                kb_id=kb.id,
                filename="x.txt",
                chunks=chunks,
                embeddings=embeddings,
                embedding_model="test-embedding",
            )
