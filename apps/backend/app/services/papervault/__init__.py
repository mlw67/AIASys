"""PaperVault 服务入口。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import get_user_global_workspace_dir

from .dataset_service import PaperVaultDatasetService
from .index_service import PaperVaultIndexService
from .models import (
    PaperVaultPaper,
    PaperVaultQuery,
    PaperVaultSearchResponse,
    PaperVaultStats,
    PaperVaultStatusResponse,
    PaperVaultSyncResponse,
)
from .query_service import PaperVaultQueryService

logger = logging.getLogger(__name__)

_papervault_service: "PaperVaultService | None" = None


def get_papervault_service() -> "PaperVaultService":
    """返回全局 PaperVault 服务单例。"""
    global _papervault_service
    if _papervault_service is None:
        _papervault_service = PaperVaultService()
    return _papervault_service


class PaperVaultService:
    """PaperVault 服务门面，协调下载、索引、查询。"""

    PAPERVAULT_DIR_NAME = ".aiasys/papervault"

    def __init__(self) -> None:
        self._base_dir_cache: dict[str, Path] = {}

    def _base_dir(self, user_id: str) -> Path:
        if user_id not in self._base_dir_cache:
            global_dir = get_user_global_workspace_dir(user_id)
            self._base_dir_cache[user_id] = global_dir / self.PAPERVAULT_DIR_NAME
        return self._base_dir_cache[user_id]

    def _dataset_service(self, user_id: str) -> PaperVaultDatasetService:
        return PaperVaultDatasetService(self._base_dir(user_id))

    def _index_service(self, user_id: str) -> PaperVaultIndexService:
        return PaperVaultIndexService(self._base_dir(user_id))

    def _query_service(self, user_id: str) -> PaperVaultQueryService:
        return PaperVaultQueryService(self._base_dir(user_id))

    def status(self, user_id: str) -> PaperVaultStatusResponse:
        dataset_status = self._dataset_service(user_id).status()
        index_status = self._index_service(user_id).status()
        return PaperVaultStatusResponse(
            ready=dataset_status["ready"] and index_status["ready"],
            downloaded=dataset_status["downloaded"],
            indexed=index_status["ready"],
            total=index_status.get("total") or dataset_status.get("total"),
            version=dataset_status.get("version"),
            remote_version=dataset_status.get("remote_version"),
            updated_at=dataset_status.get("updated_at"),
            needs_sync=dataset_status.get("needs_sync", False),
        )

    def sync(self, user_id: str, *, force: bool = False) -> PaperVaultSyncResponse:
        dataset = self._dataset_service(user_id)
        index = self._index_service(user_id)

        sync_result = dataset.sync(force=force)
        if not sync_result["success"]:
            return PaperVaultSyncResponse(
                success=False,
                downloaded=sync_result.get("downloaded", False),
                indexed=False,
                total=None,
                version=sync_result.get("version"),
                message=sync_result.get("message", "同步失败"),
            )

        # 如果下载了数据或索引不存在，重建索引
        index_ready = index.status()["ready"]
        needs_index = sync_result.get("downloaded") or not index_ready
        if needs_index:
            # 只要下载了新数据，或者索引不存在，都强制重建
            build_force = force or sync_result.get("downloaded", False) or not index_ready
            build_result = index.build(force=build_force)
            total = build_result.get("total")
            # 更新 version.json 中的 indexed_total
            version = dataset._read_version()
            version["indexed_total"] = total
            dataset._write_version(version)
            return PaperVaultSyncResponse(
                success=True,
                downloaded=sync_result.get("downloaded", False),
                indexed=True,
                total=total,
                version=sync_result.get("version"),
                message=f"{sync_result.get('message', '')} {build_result.get('message', '')}".strip(),
            )

        return PaperVaultSyncResponse(
            success=True,
            downloaded=sync_result.get("downloaded", False),
            indexed=False,
            total=index.status().get("total"),
            version=sync_result.get("version"),
            message=sync_result.get("message", "同步完成"),
        )

    def search(self, user_id: str, query: PaperVaultQuery) -> tuple[list[PaperVaultPaper], int]:
        return self._query_service(user_id).search(query)

    def stats(
        self,
        user_id: str,
        *,
        conf: list[str] | None = None,
        since: int | None = None,
        until: int | None = None,
    ) -> PaperVaultStats:
        return self._query_service(user_id).stats(conf=conf, since=since, until=until)

    def list_confs(self, user_id: str) -> list[str]:
        return self._query_service(user_id).list_confs()

    def ensure_ready(self, user_id: str) -> dict[str, Any]:
        """如果尚未下载，自动执行一次同步。用于 Agent 工具调用。"""
        status = self.status(user_id)
        if status.ready:
            return {"synced": False, "status": status}
        return {"synced": True, "result": self.sync(user_id)}


__all__ = [
    "get_papervault_service",
    "PaperVaultService",
    "PaperVaultDatasetService",
    "PaperVaultIndexService",
    "PaperVaultQueryService",
    "PaperVaultPaper",
    "PaperVaultQuery",
    "PaperVaultSearchResponse",
    "PaperVaultStats",
    "PaperVaultStatusResponse",
    "PaperVaultSyncResponse",
]
