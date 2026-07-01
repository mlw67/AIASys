"""PaperVault 数据模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PaperVaultPaper(BaseModel):
    """单篇论文元数据。"""

    id: str = Field(..., description="稳定论文 ID")
    conf: str = Field(..., description="会议/期刊 + 年份，如 ICML2024")
    year: int = Field(..., description="发表年份")
    title: str = Field(..., description="论文标题")
    authors: list[str] = Field(default_factory=list, description="作者列表")
    abstract: str | None = Field(None, description="论文摘要，可能为空")
    url: str = Field(..., description="论文详情页 URL")
    code_url: str | None = Field(None, description="开源代码仓库 URL")
    has_code: bool = Field(False, description="是否有代码链接")


class PaperVaultQuery(BaseModel):
    """PaperVault 搜索查询参数。"""

    query: str | None = Field(None, description="搜索关键词或短语")
    field: Literal["any", "title", "abstract", "author"] = Field(
        default="any", description="搜索字段"
    )
    conf: list[str] | None = Field(None, description="会议筛选列表")
    since: int | None = Field(None, ge=1900, le=2100, description="起始年份")
    until: int | None = Field(None, ge=1900, le=2100, description="结束年份")
    has_code: bool | None = Field(None, description="是否只返回有代码链接的论文")
    limit: int = Field(default=20, ge=1, le=100, description="返回数量上限")
    offset: int = Field(default=0, ge=0, description="分页偏移")
    sort: Literal["relevance", "year", "-year", "conf", "-conf", "title", "-title"] = Field(
        default="-year", description="排序方式"
    )


class PaperVaultStats(BaseModel):
    """PaperVault 统计信息。"""

    total: int = Field(..., description="论文总数")
    with_abstract: int = Field(..., description="含摘要的论文数")
    with_code: int = Field(..., description="含代码链接的论文数")
    yearly: dict[int, int] = Field(default_factory=dict, description="每年论文数")
    confs: dict[str, int] = Field(default_factory=dict, description="每个会议论文数")


class PaperVaultStatusResponse(BaseModel):
    """数据集状态响应。"""

    ready: bool = Field(..., description="是否已下载并索引")
    downloaded: bool = Field(..., description="是否已下载原始数据")
    indexed: bool = Field(..., description="是否已构建索引")
    total: int | None = Field(None, description="索引中的论文总数")
    version: str | None = Field(None, description="本地数据集版本/etag")
    remote_version: str | None = Field(None, description="远端数据集版本/etag")
    updated_at: str | None = Field(None, description="本地最后更新时间 ISO 字符串")
    needs_sync: bool = Field(False, description="是否需要同步")


class PaperVaultSyncResponse(BaseModel):
    """同步响应。"""

    success: bool = Field(..., description="是否成功")
    downloaded: bool = Field(..., description="是否执行了下载")
    indexed: bool = Field(..., description="是否执行了索引重建")
    total: int | None = Field(None, description="索引后的论文总数")
    version: str | None = Field(None, description="同步后的版本")
    message: str = Field(..., description="状态描述")


class PaperVaultSearchResponse(BaseModel):
    """论文搜索响应。"""

    total: int = Field(..., description="匹配总数")
    limit: int = Field(..., description="本次返回数量上限")
    offset: int = Field(..., description="本次分页偏移")
    papers: list[PaperVaultPaper] = Field(default_factory=list, description="论文列表")
