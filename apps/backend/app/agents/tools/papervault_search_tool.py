"""PaperVault 论文搜索工具。"""

from __future__ import annotations

from typing import Any

from app.core.agent_tool import AiasysTool, ToolResult
from app.services.papervault import get_papervault_service
from app.services.papervault.models import PaperVaultQuery


class PaperVaultSearch(AiasysTool):
    """在 PaperVault 论文元数据数据库中搜索学术论文。"""

    name = "PaperVaultSearch"
    description = (
        "在 PaperVault 论文元数据数据库中搜索学术论文。"
        "用于文献调研、综述准备、趋势分析、代码复现推荐。"
        "支持按标题、摘要、作者、会议、年份、是否有代码链接等条件筛选。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或短语，如 'federated learning'。支持多个关键词，会用 AND 连接。",
            },
            "field": {
                "type": "string",
                "enum": ["any", "title", "abstract", "author"],
                "default": "any",
                "description": "搜索字段：any（标题/摘要/作者）、title、abstract、author。",
            },
            "conf": {
                "type": "string",
                "description": "会议筛选，多个用逗号分隔。支持完整会议名如 ICML2024，也支持系列前缀如 ICML。",
            },
            "since": {
                "type": "integer",
                "description": "起始年份。",
            },
            "until": {
                "type": "integer",
                "description": "结束年份。",
            },
            "has_code": {
                "type": "boolean",
                "description": "是否只返回有开源代码链接的论文。",
            },
            "limit": {
                "type": "integer",
                "default": 20,
                "minimum": 1,
                "maximum": 100,
                "description": "返回数量上限，默认 20，最大 100。",
            },
            "sort": {
                "type": "string",
                "enum": ["relevance", "year", "-year", "conf", "-conf", "title", "-title"],
                "default": "-year",
                "description": "排序方式：relevance（相关度）、year（年份升序）、-year（年份降序）、conf、-conf、title、-title。默认 -year。",
            },
        },
        "required": ["query"],
    }

    async def invoke(
        self,
        ctx: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        ctx = ctx or {}
        user_id = str(ctx.get("user_id") or "").strip()
        if not user_id:
            return ToolResult(
                content="当前上下文缺少 user_id，无法使用 PaperVault 搜索。", is_error=True
            )

        try:
            service = get_papervault_service()
            ready = service.status(user_id).ready
            if not ready:
                sync_result = service.sync(user_id)
                if not sync_result.success:
                    return ToolResult(
                        content=f"PaperVault 数据尚未就绪，自动同步失败：{sync_result.message}",
                        is_error=True,
                    )

            conf_list = None
            raw_conf = kwargs.get("conf")
            if isinstance(raw_conf, str) and raw_conf.strip():
                conf_list = [c.strip() for c in raw_conf.split(",") if c.strip()]

            query = PaperVaultQuery(
                query=kwargs.get("query"),
                field=kwargs.get("field", "any"),
                conf=conf_list,
                since=kwargs.get("since"),
                until=kwargs.get("until"),
                has_code=kwargs.get("has_code"),
                limit=kwargs.get("limit", 20),
                offset=kwargs.get("offset", 0),
                sort=kwargs.get("sort", "-year"),
            )
            papers, total = service.search(user_id, query)
            content = _format_search_result(papers, total, query.limit)
            return ToolResult(content=content)
        except Exception as exc:
            return ToolResult(content=f"PaperVault 搜索失败: {exc}", is_error=True)


def _format_search_result(papers: list[Any], total: int, limit: int) -> str:
    lines = [
        f"在 PaperVault 中找到 {total} 篇相关论文，显示前 {len(papers)} 篇（limit={limit}）：",
        "",
    ]
    if not papers:
        return "\n".join(lines + ["未找到匹配论文，建议放宽筛选条件或更换关键词。"])

    lines.append("| 年份 | 会议 | 标题 | 作者 | 代码 | 链接 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for paper in papers:
        authors = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors += " et al."
        code_link = f"[code]({paper.code_url})" if paper.code_url else "无"
        title = paper.title.replace("|", "\\|")
        lines.append(
            f"| {paper.year} | {paper.conf} | {title} | {authors} | {code_link} | [paper]({paper.url}) |"
        )

    lines.append("")
    lines.append("提示：如需查看摘要或进一步筛选，可指定 field、conf、since/until 等参数再次搜索。")
    return "\n".join(lines)
