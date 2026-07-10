"""Chroma 导入端点端到端验证脚本。"""

from __future__ import annotations

import gc
import random
import shutil
import sys
import time
from pathlib import Path

import chromadb
import requests

BASE_URL = "http://localhost:13001/api"
EMBEDDING_DIM = 1024
PROVIDER_ID = "e2e-embedding-provider"
MODEL_ID = "e2e-embedding-model"


def _random_vector(dim: int) -> list[float]:
    return [random.uniform(-1.0, 1.0) for _ in range(dim)]


def _ensure_embedding_model() -> None:
    """确保存在一个可用的 embedding 模型配置。"""
    providers_resp = requests.get(f"{BASE_URL}/llm/providers")
    providers_resp.raise_for_status()
    providers = providers_resp.json().get("providers", [])
    provider_ids = {p["id"] for p in providers}

    if PROVIDER_ID not in provider_ids:
        provider_resp = requests.post(
            f"{BASE_URL}/llm/providers",
            json={
                "id": PROVIDER_ID,
                "name": "E2E Embedding Provider",
                "type": "openai_chat_completions",
                "base_url": "http://localhost:9999",
                "api_key": "e2e-test-key",
            },
        )
        print(f"create provider: {provider_resp.status_code}")
        provider_resp.raise_for_status()

    models_resp = requests.get(f"{BASE_URL}/llm/models")
    models_resp.raise_for_status()
    models = models_resp.json().get("models", [])
    model_ids = {m["id"] for m in models}

    if MODEL_ID not in model_ids:
        model_resp = requests.post(
            f"{BASE_URL}/llm/models",
            json={
                "id": MODEL_ID,
                "name": "E2E Embedding Model",
                "provider": PROVIDER_ID,
                "model": "e2e-embedding",
                "model_type": "embedding",
                "dimension": EMBEDDING_DIM,
                "max_context_size": 8192,
            },
        )
        print(f"create model: {model_resp.status_code}")
        model_resp.raise_for_status()


def _create_kb(name: str) -> str:
    kb_resp = requests.post(
        f"{BASE_URL}/knowledge/bases",
        json={
            "name": name,
            "embedding_model": MODEL_ID,
            "default_search_mode": "hybrid",
        },
    )
    print(f"create kb '{name}': {kb_resp.status_code}")
    kb_resp.raise_for_status()
    kb_id = kb_resp.json()["id"]
    print(f"kb_id: {kb_id}")
    return kb_id


def _import_chroma(kb_id: str, persist_dir: Path, collection_name: str | None) -> dict:
    payload: dict = {
        "chroma_persist_dir": str(persist_dir),
        "embedding_model": MODEL_ID,
        "document_source_key": "source",
    }
    if collection_name:
        payload["collection_name"] = collection_name
    import_resp = requests.post(
        f"{BASE_URL}/knowledge/bases/{kb_id}/import/chroma",
        json=payload,
    )
    print(f"import (collection={collection_name}): {import_resp.status_code}")
    print(import_resp.text)
    import_resp.raise_for_status()
    return import_resp.json()


def main() -> None:
    test_dir = Path(__file__).with_name(f".chroma-e2e-test-{int(time.time())}")
    persist_dir = test_dir / "chroma_data"
    try:
        persist_dir.mkdir(parents=True, exist_ok=True)

        _ensure_embedding_model()

        client = chromadb.PersistentClient(path=str(persist_dir))

        col1 = client.create_collection("test_docs")
        col1.add(
            ids=["c-1", "c-2", "c-3"],
            documents=["hello world", "foo bar", "hello again"],
            embeddings=[_random_vector(EMBEDDING_DIM) for _ in range(3)],
            metadatas=[
                {"source": "a.txt"},
                {"source": "a.txt"},
                {"source": "b.txt"},
            ],
        )

        col2 = client.create_collection("other_docs")
        col2.add(
            ids=["o-1"],
            documents=["chroma all collections"],
            embeddings=[_random_vector(EMBEDDING_DIM)],
            metadatas=[{"source": "c.txt"}],
        )

        del client
        gc.collect()

        # 测试 1：指定 collection 导入
        kb_id_single = _create_kb("chroma-e2e-single")
        result_single = _import_chroma(kb_id_single, persist_dir, "test_docs")
        assert result_single["success"] is True, result_single
        assert result_single["imported_documents"] == 2
        assert result_single["total_documents"] == 2
        assert sum(r["chunk_count"] for r in result_single["results"]) == 3
        for r in result_single["results"]:
            assert r["collection_name"] == "test_docs"

        docs_single = requests.get(f"{BASE_URL}/knowledge/bases/{kb_id_single}/docs").json()
        assert len(docs_single) == 2

        # 测试 2：导入所有 collection
        kb_id_all = _create_kb("chroma-e2e-all")
        result_all = _import_chroma(kb_id_all, persist_dir, None)
        assert result_all["success"] is True, result_all
        assert result_all["imported_documents"] == 3  # a.txt, b.txt, c.txt
        assert result_all["total_documents"] == 3
        assert sum(r["chunk_count"] for r in result_all["results"]) == 4

        collections_in_results = {r["collection_name"] for r in result_all["results"]}
        assert collections_in_results == {"test_docs", "other_docs"}

        docs_all = requests.get(f"{BASE_URL}/knowledge/bases/{kb_id_all}/docs").json()
        assert len(docs_all) == 3

        query_resp = requests.post(
            f"{BASE_URL}/knowledge/bases/{kb_id_all}/query",
            json={"query": "hello", "top_k": 3, "search_mode": "fulltext"},
        )
        query_resp.raise_for_status()
        query = query_resp.json()
        print(f"search results: {len(query['results'])}")
        assert len(query["results"]) > 0

        print("\n[OK] Chroma import e2e test passed")
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"\n[FAIL] assertion: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[FAIL] error: {exc}", file=sys.stderr)
        sys.exit(1)
