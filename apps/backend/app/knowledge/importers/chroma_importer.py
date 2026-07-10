"""Chroma Vector Database 原生磁盘存储导入器。

通过 ``chromadb.PersistentClient`` 读取 Chroma 持久化目录，
将 collection 中的 documents / embeddings / metadatas 映射为
AIASys 知识库可接收的 chunk + embedding 格式。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ChromaImportError(Exception):
    """Chroma 导入相关异常。"""


def _validate_chroma_dir(persist_dir: str) -> Path:
    """校验 Chroma 持久化目录是否包含必要的 chroma.sqlite3 文件。"""
    path = Path(persist_dir)
    if not path.is_dir():
        raise ChromaImportError(f"Chroma 持久化目录不存在: {persist_dir}")
    sqlite_file = path / "chroma.sqlite3"
    if not sqlite_file.is_file():
        raise ChromaImportError(
            f"目录 {persist_dir} 不是有效的 Chroma 持久化目录，" "未找到 chroma.sqlite3"
        )
    return path


def list_chroma_collections(persist_dir: str) -> list[str]:
    """列出 Chroma 持久化目录下所有 collection 名称。

    Args:
        persist_dir: Chroma 持久化目录路径。

    Returns:
        collection 名称列表。
    """
    try:
        import chromadb
    except ImportError as exc:
        raise ChromaImportError(
            "未安装 chromadb，无法读取 Chroma 原生磁盘存储。"
            "请在 apps/backend 执行: uv add chromadb"
        ) from exc

    _validate_chroma_dir(persist_dir)

    try:
        client = chromadb.PersistentClient(path=persist_dir)
        collections = client.list_collections()
    except Exception as exc:
        raise ChromaImportError(f"列出 Chroma collections 失败: {exc}") from exc

    names: list[str] = []
    for col in collections:
        if isinstance(col, str):
            names.append(col)
            continue
        try:
            names.append(str(col.name))
        except Exception:
            names.append(str(col))
    return names


def _decode_float32_vector(blob: bytes) -> list[float]:
    """将 FLOAT32 字节序列解码为 float 列表。"""
    if len(blob) % 4 != 0:
        raise ChromaImportError("向量 BLOB 长度不是 4 的倍数，无法按 FLOAT32 解码")
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


def _get_collection_topic(persist_dir: str, collection_name: str) -> Optional[str]:
    """从 chroma.sqlite3 查询 collection 对应的 embeddings_queue topic。

    topic 格式在 Chroma 内部可能为 ``persistent://<tenant>/<database>/<collection_id>``，
    这里通过 collection id 后缀匹配，避免硬编码 tenant/database 名称。
    """
    sqlite_path = Path(persist_dir) / "chroma.sqlite3"
    try:
        conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    except Exception:
        return None
    try:
        row = conn.execute(
            "SELECT id FROM collections WHERE name = ?", (collection_name,)
        ).fetchone()
        if not row:
            return None
        collection_id = row[0]
        topic_row = conn.execute(
            "SELECT DISTINCT topic FROM embeddings_queue WHERE topic LIKE ?",
            (f"%/{collection_id}",),
        ).fetchone()
        return topic_row[0] if topic_row else None
    except Exception:
        return None
    finally:
        conn.close()


def _read_collection_from_queue(
    persist_dir: str,
    collection_name: str,
) -> dict[str, Any]:
    """HNSW 索引损坏时的降级读取：从 chroma.sqlite3 的 embeddings_queue 表还原数据。"""
    sqlite_path = Path(persist_dir) / "chroma.sqlite3"
    topic = _get_collection_topic(persist_dir, collection_name)
    if not topic:
        raise ChromaImportError(
            f"无法定位 collection '{collection_name}' 的内部 topic，无法从 sqlite 降级读取"
        )

    try:
        conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    except Exception as exc:
        raise ChromaImportError(f"无法打开 chroma.sqlite3: {exc}") from exc

    records: Dict[str, Dict[str, Any]] = {}
    try:
        rows = conn.execute(
            "SELECT operation, id, vector, encoding, metadata "
            "FROM embeddings_queue WHERE topic = ? ORDER BY seq_id",
            (topic,),
        ).fetchall()
    except Exception as exc:
        raise ChromaImportError(f"读取 embeddings_queue 失败: {exc}") from exc
    finally:
        conn.close()

    if not rows:
        raise ChromaImportError(
            f"collection '{collection_name}' 的 HNSW 索引已损坏，"
            "且 embeddings_queue 中没有可用记录（可能已被清理），无法降级读取。"
        )

    for operation, id_, vector_blob, encoding, metadata_json in rows:
        if operation == 3:  # DELETE
            records.pop(id_, None)
            continue

        if not vector_blob:
            raise ChromaImportError(f"记录 {id_} 缺少向量数据，无法从 embeddings_queue 还原")

        if encoding and encoding.upper() != "FLOAT32":
            raise ChromaImportError(f"不支持的向量编码 {encoding}，仅支持 FLOAT32")

        try:
            embedding = _decode_float32_vector(vector_blob)
        except Exception as exc:
            raise ChromaImportError(f"解码 {id_} 的向量失败: {exc}") from exc

        metadata = json.loads(metadata_json or "{}")
        document = metadata.pop("chroma:document", "")
        # 清理 chroma 内部字段
        metadata.pop("chroma:uri", None)

        records[id_] = {
            "document": document,
            "embedding": embedding,
            "metadata": metadata,
        }

    if not records:
        raise ChromaImportError(
            f"collection '{collection_name}' 在 embeddings_queue 中没有有效记录"
        )

    ids = list(records.keys())
    return {
        "ids": ids,
        "documents": [records[i]["document"] for i in ids],
        "embeddings": [records[i]["embedding"] for i in ids],
        "metadatas": [records[i]["metadata"] for i in ids],
    }


def read_chroma_collection(
    persist_dir: str,
    collection_name: str,
) -> dict[str, Any]:
    """读取 Chroma 指定 collection 的全部数据（含向量）。

    Args:
        persist_dir: Chroma 持久化目录路径。
        collection_name: 要导入的 collection 名称。

    Returns:
        形如 ``{"ids": [...], "documents": [...], "embeddings": [...], "metadatas": [...]}`` 的字典。
    """
    try:
        import chromadb
    except ImportError as exc:
        raise ChromaImportError(
            "未安装 chromadb，无法读取 Chroma 原生磁盘存储。"
            "请在 apps/backend 执行: uv add chromadb"
        ) from exc

    _validate_chroma_dir(persist_dir)

    try:
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_collection(collection_name)
        data = collection.get(
            include=["documents", "embeddings", "metadatas"],
        )
    except RuntimeError as exc:
        err_msg = str(exc)
        if "Cannot open header file" in err_msg:
            logger.warning(
                "collection '%s' 的 HNSW 索引无法加载（%s），尝试从 embeddings_queue 降级读取",
                collection_name,
                err_msg,
            )
            return _read_collection_from_queue(persist_dir, collection_name)
        raise ChromaImportError(f"读取 Chroma collection '{collection_name}' 失败: {exc}") from exc
    except Exception as exc:
        raise ChromaImportError(f"读取 Chroma collection '{collection_name}' 失败: {exc}") from exc

    # 兼容 chromadb 可能返回 numpy 数组的场景，统一转为 list
    ids = list(data.get("ids") or [])
    documents = list(data.get("documents") or [])
    embeddings_raw = data.get("embeddings")
    if embeddings_raw is None:
        embeddings_raw = []
    metadatas = list(data.get("metadatas") or [])

    embeddings: list[list[float]] = [list(map(float, emb)) for emb in embeddings_raw]

    if not (len(ids) == len(documents) == len(embeddings) == len(metadatas)):
        raise ChromaImportError(
            "Chroma 返回的数据长度不一致，无法导入。"
            f"ids={len(ids)}, documents={len(documents)}, "
            f"embeddings={len(embeddings)}, metadatas={len(metadatas)}"
        )

    logger.info(
        "从 Chroma 读取 collection '%s': %d 条记录",
        collection_name,
        len(ids),
    )
    return {
        "ids": ids,
        "documents": documents,
        "embeddings": embeddings,
        "metadatas": metadatas,
    }


def group_chroma_records_by_source(
    ids: list[str],
    documents: list[str | None],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any] | None],
    source_key: str = "source",
) -> dict[str, list[dict[str, Any]]]:
    """按 metadata 中的 source 字段将 Chroma 记录分组为文档。

    没有 source 字段的记录会被单独分组，保证每条记录都能被导入。

    Args:
        ids: Chroma 记录 ID 列表。
        documents: 文档文本列表。
        embeddings: 向量列表。
        metadatas: metadata 列表。
        source_key: 用于分组的 metadata 字段名，默认 ``source``。

    Returns:
        以 source 值为键、记录列表为值的分组字典。
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for i, chroma_id in enumerate(ids):
        metadata = dict(metadatas[i] or {})
        # 没有 source 字段时使用短后缀，避免 chroma_id 过长导致 Windows 路径/文件名问题
        source = str(metadata.get(source_key) or f"__single__{i}")
        groups.setdefault(source, []).append(
            {
                "chroma_id": chroma_id,
                "content": documents[i] or "",
                "embedding": embeddings[i],
                "metadata": {**metadata, "chroma_id": chroma_id},
            }
        )
    return groups
