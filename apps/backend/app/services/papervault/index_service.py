"""PaperVault SQLite + FTS5 索引构建服务。"""

from __future__ import annotations

import gzip
import json
import logging
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import filelock

from app.utils.path_utils import as_system_path

from .models import PaperVaultPaper

logger = logging.getLogger(__name__)


class PaperVaultIndexService:
    """负责从 cache.jsonl.gz 构建 SQLite + FTS5 索引。"""

    INSERT_BATCH = 1000
    LOCK_TIMEOUT = 600

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / "papervault.db"
        self.cache_gz_path = self.base_dir / "cache.jsonl.gz"
        self.lock_path = self.base_dir / "index.lock"

    def _ensure_dir(self) -> None:
        os.makedirs(as_system_path(self.base_dir), exist_ok=True)

    def status(self) -> dict[str, Any]:
        ready = self.db_path.exists()
        total: int | None = None
        if ready:
            try:
                with sqlite3.connect(as_system_path(self.db_path)) as conn:
                    row = conn.execute("SELECT COUNT(*) FROM papers").fetchone()
                    total = row[0] if row else None
            except Exception as exc:
                logger.warning("读取 PaperVault 索引状态失败: %s", exc)
        return {"ready": ready, "total": total}

    def build(self, *, force: bool = False) -> dict[str, Any]:
        self._ensure_dir()
        if not self.cache_gz_path.exists():
            raise FileNotFoundError("PaperVault 缓存文件不存在，请先调用 sync()")

        lock = filelock.FileLock(as_system_path(self.lock_path), timeout=self.LOCK_TIMEOUT)
        with lock:
            return self._build_locked(force=force)

    def _build_locked(self, *, force: bool = False) -> dict[str, Any]:
        if not force and self.db_path.exists():
            # 检查索引总数与缓存行数是否匹配，简单判断是否需要重建
            try:
                current_total = 0
                with sqlite3.connect(as_system_path(self.db_path)) as conn:
                    row = conn.execute("SELECT COUNT(*) FROM papers").fetchone()
                    current_total = row[0] if row else 0
                if current_total > 0:
                    return {
                        "success": True,
                        "rebuilt": False,
                        "total": current_total,
                        "message": "索引已存在且非空，如需强制重建请传 force=true。",
                    }
            except Exception:
                pass

        # 创建临时 db，构建完成后原子替换
        fd, temp_db = tempfile.mkstemp(
            dir=as_system_path(self.base_dir),
            suffix=".db.tmp",
        )
        os.close(fd)
        temp_db_path = Path(temp_db)

        try:
            total = self._build_into(temp_db_path)
            os.replace(as_system_path(temp_db_path), as_system_path(self.db_path))
        except Exception:
            try:
                temp_db_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        return {
            "success": True,
            "rebuilt": True,
            "total": total,
            "message": f"索引构建成功，共 {total} 篇论文。",
        }

    def _build_into(self, db_path: Path) -> int:
        sys_db_path = as_system_path(db_path)
        connection = sqlite3.connect(sys_db_path, isolation_level=None)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")
            self._ensure_schema(connection)

            total = 0
            with gzip.open(as_system_path(self.cache_gz_path), "rt", encoding="utf-8") as fh:
                batch: list[tuple] = []
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        paper = self._parse_line(line)
                    except Exception as exc:
                        logger.warning("解析 PaperVault 行失败: %s", exc)
                        continue

                    batch.append(
                        (
                            paper.id,
                            paper.conf,
                            paper.year,
                            paper.title,
                            json.dumps(paper.authors, ensure_ascii=False),
                            paper.abstract or "",
                            paper.url,
                            paper.code_url or "",
                            1 if paper.has_code else 0,
                        )
                    )

                    if len(batch) >= self.INSERT_BATCH:
                        self._insert_batch(connection, batch)
                        total += len(batch)
                        batch = []

                if batch:
                    self._insert_batch(connection, batch)
                    total += len(batch)

            # 重建 FTS5 索引
            connection.execute("INSERT INTO papers_fts(papers_fts) VALUES('rebuild')")
            connection.execute("ANALYZE")

            return total
        finally:
            connection.close()

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                conf TEXT NOT NULL,
                year INTEGER NOT NULL,
                title TEXT NOT NULL,
                authors TEXT NOT NULL,
                abstract TEXT,
                url TEXT NOT NULL,
                code_url TEXT,
                has_code INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_papers_conf ON papers(conf);
            CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
            CREATE INDEX IF NOT EXISTS idx_papers_has_code ON papers(has_code);

            CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
                title,
                abstract,
                authors,
                content='papers',
                content_rowid='rowid'
            );
            """
        )

    def _insert_batch(self, connection: sqlite3.Connection, batch: list[tuple]) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.executemany(
                """
                INSERT INTO papers (id, conf, year, title, authors, abstract, url, code_url, has_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def _parse_line(self, line: str) -> PaperVaultPaper:
        data = json.loads(line)
        conf = str(data.get("conf") or "").strip()
        title = str(data.get("paper_name") or "").strip()
        url = str(data.get("paper_url") or "").strip()
        if not conf or not title or not url:
            raise ValueError("缺少必要字段: conf/paper_name/paper_url")

        year = self._parse_year(conf)
        authors = data.get("paper_authors") or []
        if not isinstance(authors, list):
            authors = []
        authors = [str(a).strip() for a in authors if str(a).strip()]

        abstract = data.get("paper_abstract")
        abstract = str(abstract).strip() if abstract else None

        code_url = data.get("paper_code") or ""
        code_url = str(code_url).strip()
        if code_url == "#" or not code_url:
            code_url = None

        has_code = code_url is not None
        paper_id = f"{conf}:{self._stable_hash(url)}"

        return PaperVaultPaper(
            id=paper_id,
            conf=conf,
            year=year,
            title=title,
            authors=authors,
            abstract=abstract,
            url=url,
            code_url=code_url,
            has_code=has_code,
        )

    @staticmethod
    def _parse_year(conf: str) -> int:
        # conf 格式如 ICML2024, NeurIPS2025, ACL2023
        digits = ""
        for char in reversed(conf):
            if char.isdigit():
                digits = char + digits
            else:
                break
        if len(digits) == 4:
            return int(digits)
        if len(digits) == 2:
            year = int(digits)
            return 2000 + year if year < 50 else 1900 + year
        return 0

    @staticmethod
    def _stable_hash(text: str) -> str:
        import hashlib

        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
