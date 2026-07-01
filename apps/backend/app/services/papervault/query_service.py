"""PaperVault 查询服务。"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from app.utils.path_utils import as_system_path

from .models import PaperVaultPaper, PaperVaultQuery, PaperVaultStats

logger = logging.getLogger(__name__)


class PaperVaultQueryService:
    """负责 PaperVault SQLite 索引的搜索与统计查询。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / "papervault.db"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(as_system_path(self.db_path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def search(self, query: PaperVaultQuery) -> tuple[list[PaperVaultPaper], int]:
        if not self.db_path.exists():
            raise FileNotFoundError("PaperVault 索引不存在，请先构建索引")

        with self._connect() as connection:
            total = self._count(connection, query)
            papers = self._fetch(connection, query)
            return papers, total

    def _count(self, connection: sqlite3.Connection, query: PaperVaultQuery) -> int:
        sql, params = self._build_sql(query, count=True)
        row = connection.execute(sql, params).fetchone()
        return row[0] if row else 0

    def _fetch(
        self, connection: sqlite3.Connection, query: PaperVaultQuery
    ) -> list[PaperVaultPaper]:
        sql, params = self._build_sql(query, count=False)
        rows = connection.execute(sql, params).fetchall()
        return [self._row_to_paper(row) for row in rows]

    def _build_sql(self, query: PaperVaultQuery, *, count: bool) -> tuple[str, list[Any]]:
        params: list[Any] = []
        where_clauses: list[str] = []
        join_fts = False
        fts_where: str | None = None
        fts_rank: str | None = None

        # 文本搜索
        if query.query and query.query.strip():
            clean_query = self._escape_fts(query.query.strip())
            if clean_query:
                join_fts = True
                if query.field == "any":
                    fts_where = "papers_fts MATCH ?"
                    params.append(clean_query)
                elif query.field == "title":
                    fts_where = "papers_fts.title MATCH ?"
                    params.append(clean_query)
                elif query.field == "abstract":
                    fts_where = "papers_fts.abstract MATCH ?"
                    params.append(clean_query)
                elif query.field == "author":
                    fts_where = "papers_fts.authors MATCH ?"
                    params.append(clean_query)
                fts_rank = "rank"

        # 会议筛选（支持完整 conf 如 ICML2024，也支持系列前缀如 ICML）
        if query.conf:
            conf_condition, conf_params = self._build_conf_condition(
                query.conf, table_alias="papers"
            )
            where_clauses.append(conf_condition)
            params.extend(conf_params)

        # 年份筛选
        if query.since is not None:
            where_clauses.append("papers.year >= ?")
            params.append(query.since)
        if query.until is not None:
            where_clauses.append("papers.year <= ?")
            params.append(query.until)

        # 代码链接筛选
        if query.has_code is not None:
            where_clauses.append("papers.has_code = ?")
            params.append(1 if query.has_code else 0)

        # 组装 FROM/JOIN
        if join_fts:
            from_clause = "FROM papers JOIN papers_fts ON papers.rowid = papers_fts.rowid"
            if fts_where:
                where_clauses.insert(0, fts_where)
        else:
            from_clause = "FROM papers"

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        if count:
            sql = f"SELECT COUNT(*) {from_clause} {where_sql}"
            return sql, params

        # 排序
        order_by = self._build_order_by(query, fts_rank)
        limit_offset = "LIMIT ? OFFSET ?"
        params.extend([query.limit, query.offset])

        sql = f"SELECT papers.* {from_clause} {where_sql} {order_by} {limit_offset}"
        return sql, params

    @staticmethod
    def _build_order_by(query: PaperVaultQuery, fts_rank: str | None) -> str:
        sort = query.sort
        if sort == "relevance" and fts_rank:
            return "ORDER BY papers_fts.rank"
        if sort == "year":
            return "ORDER BY papers.year ASC"
        if sort == "-year":
            return "ORDER BY papers.year DESC"
        if sort == "conf":
            return "ORDER BY papers.conf ASC"
        if sort == "-conf":
            return "ORDER BY papers.conf DESC"
        if sort == "title":
            return "ORDER BY papers.title ASC"
        if sort == "-title":
            return "ORDER BY papers.title DESC"
        # 默认按年份倒序
        return "ORDER BY papers.year DESC, papers.title ASC"

    @staticmethod
    def _escape_fts(text: str) -> str:
        """转义 FTS5 查询中的特殊字符，并把多词变成 AND 查询。"""
        # FTS5 特殊字符: " * ( ) - /
        # 简单处理：去掉特殊字符，用空格分词后拼接成 NEAR/AND 查询
        cleaned = ""
        for char in text:
            if char.isalnum() or char in " \u4e00-\u9fff":
                cleaned += char
            else:
                cleaned += " "
        tokens = [t.strip() for t in cleaned.split() if t.strip()]
        if not tokens:
            return ""
        # 用 AND 连接，保证所有词都出现
        if len(tokens) == 1:
            return tokens[0]
        return " AND ".join(tokens)

    def _row_to_paper(self, row: sqlite3.Row) -> PaperVaultPaper:
        authors_raw = row["authors"]
        try:
            authors = json.loads(authors_raw) if authors_raw else []
        except json.JSONDecodeError:
            authors = []
        if not isinstance(authors, list):
            authors = []

        code_url = row["code_url"]
        if not code_url:
            code_url = None

        return PaperVaultPaper(
            id=row["id"],
            conf=row["conf"],
            year=row["year"],
            title=row["title"],
            authors=authors,
            abstract=row["abstract"] or None,
            url=row["url"],
            code_url=code_url,
            has_code=bool(row["has_code"]),
        )

    def stats(
        self,
        *,
        conf: list[str] | None = None,
        since: int | None = None,
        until: int | None = None,
    ) -> PaperVaultStats:
        if not self.db_path.exists():
            raise FileNotFoundError("PaperVault 索引不存在，请先构建索引")

        with self._connect() as connection:
            where_clauses: list[str] = []
            params: list[Any] = []

            if conf:
                conf_condition, conf_params = self._build_conf_condition(conf, table_alias="")
                where_clauses.append(conf_condition)
                params.extend(conf_params)
            if since is not None:
                where_clauses.append("year >= ?")
                params.append(since)
            if until is not None:
                where_clauses.append("year <= ?")
                params.append(until)

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            total_row = connection.execute(
                f"SELECT COUNT(*) FROM papers {where_sql}", params
            ).fetchone()
            total = total_row[0] if total_row else 0

            abstract_clauses = list(where_clauses)
            abstract_clauses.append("abstract IS NOT NULL AND abstract != ''")
            abstract_where_sql = "WHERE " + " AND ".join(abstract_clauses)
            with_abstract_row = connection.execute(
                f"SELECT COUNT(*) FROM papers {abstract_where_sql}", list(params)
            ).fetchone()
            with_abstract = with_abstract_row[0] if with_abstract_row else 0

            code_clauses = list(where_clauses)
            code_clauses.append("has_code = 1")
            code_where_sql = "WHERE " + " AND ".join(code_clauses)
            with_code_row = connection.execute(
                f"SELECT COUNT(*) FROM papers {code_where_sql}", list(params)
            ).fetchone()
            with_code = with_code_row[0] if with_code_row else 0

            yearly_rows = connection.execute(
                f"SELECT year, COUNT(*) FROM papers {where_sql} GROUP BY year ORDER BY year",
                list(params),
            ).fetchall()
            yearly = {row[0]: row[1] for row in yearly_rows if row[0]}

            conf_rows = connection.execute(
                f"SELECT conf, COUNT(*) FROM papers {where_sql} GROUP BY conf ORDER BY conf",
                list(params),
            ).fetchall()
            confs = {row[0]: row[1] for row in conf_rows if row[0]}

            return PaperVaultStats(
                total=total,
                with_abstract=with_abstract,
                with_code=with_code,
                yearly=yearly,
                confs=confs,
            )

    @staticmethod
    def _build_conf_condition(
        conf_list: list[str], *, table_alias: str = "papers"
    ) -> tuple[str, list[str]]:
        """构建会议筛选条件。

        - 以 4 位年份结尾（如 ICML2024）按精确匹配处理；
        - 否则按系列前缀匹配（如 ICML 匹配 ICML2023、ICML2024 等）。
        """
        import re

        alias = f"{table_alias}." if table_alias else ""
        conditions: list[str] = []
        params: list[str] = []
        for c in conf_list:
            c = c.strip()
            if not c:
                continue
            if re.search(r"\d{4}$", c):
                conditions.append(f"{alias}conf = ?")
                params.append(c)
            else:
                conditions.append(f"{alias}conf LIKE ?")
                params.append(f"{c}%")
        return "(" + " OR ".join(conditions) + ")", params

    def list_confs(self) -> list[str]:
        if not self.db_path.exists():
            raise FileNotFoundError("PaperVault 索引不存在，请先构建索引")

        with self._connect() as connection:
            rows = connection.execute("SELECT DISTINCT conf FROM papers ORDER BY conf").fetchall()
            return [row[0] for row in rows if row[0]]
