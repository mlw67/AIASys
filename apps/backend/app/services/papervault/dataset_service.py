"""PaperVault HF 数据集下载与版本同步服务。"""

from __future__ import annotations

import gzip
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import filelock
from huggingface_hub import hf_hub_download
from huggingface_hub.hf_api import HfApi

from app.utils.path_utils import as_system_path, atomic_write_text

logger = logging.getLogger(__name__)


class PaperVaultDatasetService:
    """负责 PaperVault HF 数据集的下载、解压、版本同步。"""

    DATASET_REPO = "youngfish42/PaperVault"
    CACHE_FILE = "cache/cache.jsonl.gz"
    LOCK_TIMEOUT = 600

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    @property
    def cache_gz_path(self) -> Path:
        return self.base_dir / "cache.jsonl.gz"

    @property
    def version_path(self) -> Path:
        return self.base_dir / "version.json"

    @property
    def lock_path(self) -> Path:
        return self.base_dir / "sync.lock"

    def _ensure_dir(self) -> None:
        os.makedirs(as_system_path(self.base_dir), exist_ok=True)

    def _read_version(self) -> dict[str, Any]:
        if not self.version_path.exists():
            return {}
        try:
            content = self.version_path.read_text(encoding="utf-8")
            return json.loads(content) if content.strip() else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("读取 PaperVault 版本文件失败: %s", exc)
            return {}

    def _write_version(self, payload: dict[str, Any]) -> None:
        self._ensure_dir()
        atomic_write_text(self.version_path, json.dumps(payload, ensure_ascii=False, indent=2))

    def _get_remote_etag(self) -> str | None:
        """获取远端版本标识。

        HF Dataset 文件不一定暴露 etag，因此优先使用 last_commit.oid 作为版本标识。
        """
        try:
            api = HfApi()
            paths = api.get_paths_info(
                repo_id=self.DATASET_REPO,
                paths=[self.CACHE_FILE],
                repo_type="dataset",
                expand=True,
            )
            for info in paths:
                if getattr(info, "etag", None):
                    return str(info.etag)
                last_commit = getattr(info, "last_commit", None)
                if last_commit and getattr(last_commit, "oid", None):
                    return str(last_commit.oid)
        except Exception as exc:
            logger.warning("获取 PaperVault 远端版本标识失败: %s", exc)
        return None

    def status(self) -> dict[str, Any]:
        self._ensure_dir()
        version = self._read_version()
        downloaded = self.cache_gz_path.exists() and self.cache_gz_path.stat().st_size > 0
        indexed = (self.base_dir / "papervault.db").exists()
        total = version.get("indexed_total") if indexed else None
        remote_etag = self._get_remote_etag()
        local_etag = version.get("etag")
        needs_sync = bool(remote_etag and remote_etag != local_etag)

        return {
            "ready": downloaded and indexed,
            "downloaded": downloaded,
            "indexed": indexed,
            "total": total,
            "version": local_etag,
            "remote_version": remote_etag,
            "updated_at": version.get("updated_at"),
            "needs_sync": needs_sync,
        }

    def sync(self, *, force: bool = False) -> dict[str, Any]:
        self._ensure_dir()
        lock = filelock.FileLock(as_system_path(self.lock_path), timeout=self.LOCK_TIMEOUT)
        with lock:
            return self._sync_locked(force=force)

    def _sync_locked(self, *, force: bool = False) -> dict[str, Any]:
        version = self._read_version()
        local_etag = version.get("etag")
        remote_etag = self._get_remote_etag()

        needs_download = force
        if not needs_download and not self.cache_gz_path.exists():
            needs_download = True
        if not needs_download and remote_etag and remote_etag != local_etag:
            needs_download = True

        if not needs_download:
            return {
                "success": True,
                "downloaded": False,
                "indexed": False,
                "total": version.get("indexed_total"),
                "version": local_etag,
                "message": "本地数据已是最新版本，无需同步。",
            }

        # 下载到临时位置，原子替换
        self._ensure_dir()
        fd, temp_path = tempfile.mkstemp(
            dir=as_system_path(self.base_dir),
            suffix=".jsonl.gz.tmp",
        )
        os.close(fd)
        temp_path_obj = Path(temp_path)
        try:
            downloaded_path = hf_hub_download(
                repo_id=self.DATASET_REPO,
                filename=self.CACHE_FILE,
                repo_type="dataset",
                local_dir=as_system_path(self.base_dir),
                local_dir_use_symlinks=False,
                force_download=force,
            )
            # hf_hub_download 会按仓库结构保存，我们复制/重命名为 cache.jsonl.gz
            downloaded_path_obj = Path(downloaded_path)
            if downloaded_path_obj.exists():
                os.replace(as_system_path(downloaded_path_obj), as_system_path(self.cache_gz_path))
        finally:
            try:
                temp_path_obj.unlink(missing_ok=True)
            except OSError:
                pass

        # 基础校验：能解压一行即认为成功
        self._validate_cache_file()

        now = datetime.now(timezone.utc).isoformat()
        version = {
            "etag": remote_etag or "unknown",
            "updated_at": now,
            "indexed_total": None,
        }
        self._write_version(version)

        return {
            "success": True,
            "downloaded": True,
            "indexed": False,
            "total": None,
            "version": version["etag"],
            "message": "数据集下载成功，等待构建索引。",
        }

    def _validate_cache_file(self) -> None:
        sys_path = as_system_path(self.cache_gz_path)
        try:
            with gzip.open(sys_path, "rt", encoding="utf-8") as fh:
                first_line = fh.readline()
                if not first_line.strip():
                    raise ValueError("cache.jsonl.gz 为空")
                json.loads(first_line)
        except Exception as exc:
            raise ValueError(f"PaperVault 缓存文件校验失败: {exc}") from exc

    def get_cache_gz_path(self) -> Path:
        return self.cache_gz_path
