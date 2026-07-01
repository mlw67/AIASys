"""PaperVault 科研论文元数据 API。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_auth
from app.models.user import UserInfo
from app.services.papervault import (
    PaperVaultQuery,
    PaperVaultSearchResponse,
    PaperVaultStats,
    PaperVaultStatusResponse,
    PaperVaultSyncResponse,
    get_papervault_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/papervault", tags=["research"])


@router.get("/status", response_model=PaperVaultStatusResponse)
async def get_papervault_status(
    current_user: UserInfo = Depends(require_auth()),
) -> PaperVaultStatusResponse:
    """获取 PaperVault 数据集本地状态。"""
    try:
        return get_papervault_service().status(current_user.user_id)
    except Exception as exc:
        logger.exception("获取 PaperVault 状态失败")
        raise HTTPException(status_code=500, detail=f"获取 PaperVault 状态失败: {exc}") from exc


@router.post("/sync", response_model=PaperVaultSyncResponse)
async def sync_papervault(
    force: bool = False,
    current_user: UserInfo = Depends(require_auth()),
) -> PaperVaultSyncResponse:
    """手动触发 PaperVault 数据集同步与索引重建。"""
    try:
        return get_papervault_service().sync(current_user.user_id, force=force)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("同步 PaperVault 失败")
        raise HTTPException(status_code=500, detail=f"同步 PaperVault 失败: {exc}") from exc


@router.get("/papers", response_model=PaperVaultSearchResponse)
async def search_papers(
    query: str | None = None,
    field: str = "any",
    conf: list[str] | None = Query(default=None),
    since: int | None = None,
    until: int | None = None,
    has_code: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    sort: str = "-year",
    current_user: UserInfo = Depends(require_auth()),
) -> PaperVaultSearchResponse:
    """搜索 PaperVault 论文元数据。"""
    try:
        q = PaperVaultQuery(
            query=query,
            field=field,  # type: ignore[arg-type]
            conf=conf,
            since=since,
            until=until,
            has_code=has_code,
            limit=limit,
            offset=offset,
            sort=sort,  # type: ignore[arg-type]
        )
        papers, total = get_papervault_service().search(current_user.user_id, q)
        return PaperVaultSearchResponse(
            total=total,
            limit=limit,
            offset=offset,
            papers=papers,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{exc}。请先调用 POST /api/research/papervault/sync 下载并构建索引。",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("搜索 PaperVault 失败")
        raise HTTPException(status_code=500, detail=f"搜索 PaperVault 失败: {exc}") from exc


@router.get("/confs")
async def list_confs(
    current_user: UserInfo = Depends(require_auth()),
) -> list[str]:
    """列出 PaperVault 中所有会议/期刊系列。"""
    try:
        return get_papervault_service().list_confs(current_user.user_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{exc}。请先调用 POST /api/research/papervault/sync 下载并构建索引。",
        ) from exc
    except Exception as exc:
        logger.exception("列出 PaperVault 会议失败")
        raise HTTPException(status_code=500, detail=f"列出会议失败: {exc}") from exc


@router.get("/stats", response_model=PaperVaultStats)
async def get_stats(
    conf: list[str] | None = Query(default=None),
    since: int | None = None,
    until: int | None = None,
    current_user: UserInfo = Depends(require_auth()),
) -> PaperVaultStats:
    """获取 PaperVault 数据集统计信息。"""
    try:
        return get_papervault_service().stats(
            current_user.user_id, conf=conf, since=since, until=until
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{exc}。请先调用 POST /api/research/papervault/sync 下载并构建索引。",
        ) from exc
    except Exception as exc:
        logger.exception("获取 PaperVault 统计失败")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {exc}") from exc
