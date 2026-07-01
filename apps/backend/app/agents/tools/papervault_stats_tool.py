"""PaperVault 统计工具。"""

from __future__ import annotations

from typing import Any

from app.core.agent_tool import AiasysTool, ToolResult
from app.services.papervault import get_papervault_service


class PaperVaultStats(AiasysTool):
    """获取 PaperVault 数据集的统计信息，用于趋势分析和报告生成。"""

    name = "PaperVaultStats"
    description = (
        "获取 PaperVault 论文元数据数据集的统计信息。"
        "可统计总量、含摘要/代码比例、年度分布、会议分布。"
        "用于趋势分析、领域报告、科研选题。"
    )
    parameters = {
        "type": "object",
        "properties": {
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
        },
        "required": [],
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
                content="当前上下文缺少 user_id，无法使用 PaperVault 统计。", is_error=True
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

            stats = service.stats(
                user_id,
                conf=conf_list,
                since=kwargs.get("since"),
                until=kwargs.get("until"),
            )
            content = _format_stats_result(stats)
            return ToolResult(content=content)
        except Exception as exc:
            return ToolResult(content=f"PaperVault 统计失败: {exc}", is_error=True)


def _format_stats_result(stats: Any) -> str:
    lines = ["PaperVault 数据集统计：", ""]
    lines.append(f"- 论文总数：{stats.total}")
    lines.append(f"- 含摘要：{stats.with_abstract} ({_pct(stats.with_abstract, stats.total)})")
    lines.append(f"- 含代码链接：{stats.with_code} ({_pct(stats.with_code, stats.total)})")

    if stats.yearly:
        lines.append("")
        lines.append("年度分布（年份: 数量）：")
        for year in sorted(stats.yearly.keys(), reverse=True)[:10]:
            lines.append(f"- {year}: {stats.yearly[year]}")

    if stats.confs:
        lines.append("")
        lines.append("会议分布（Top 10）：")
        sorted_confs = sorted(stats.confs.items(), key=lambda x: x[1], reverse=True)[:10]
        for conf, count in sorted_confs:
            lines.append(f"- {conf}: {count}")

    return "\n".join(lines)


def _pct(part: int, total: int) -> str:
    if total <= 0:
        return "N/A"
    return f"{part / total * 100:.1f}%"
