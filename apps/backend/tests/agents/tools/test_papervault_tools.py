"""PaperVault Agent 工具测试。"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from app.agents.tools.papervault_search_tool import PaperVaultSearch
from app.agents.tools.papervault_stats_tool import PaperVaultStats
from app.services.papervault.index_service import PaperVaultIndexService

SAMPLE_PAPERS = [
    {
        "conf": "ICML2024",
        "paper_name": "Federated Learning for Vision",
        "paper_authors": ["Alice Smith", "Bob Jones"],
        "paper_url": "http://example.com/1",
        "paper_abstract": "We study federated learning in computer vision.",
        "paper_code": "https://github.com/foo/bar",
    },
    {
        "conf": "NeurIPS2023",
        "paper_name": "Federated Optimization Methods",
        "paper_authors": ["Carol White"],
        "paper_url": "http://example.com/2",
        "paper_abstract": "Optimization techniques in federated settings.",
        "paper_code": "#",
    },
]


@pytest.fixture
def indexed_dir(tmp_path: Path) -> Path:
    base = tmp_path / "papervault"
    base.mkdir(parents=True)
    cache_path = base / "cache.jsonl.gz"
    with gzip.open(cache_path, "wt", encoding="utf-8") as fh:
        for paper in SAMPLE_PAPERS:
            fh.write(json.dumps(paper) + "\n")
    PaperVaultIndexService(base).build(force=True)
    return base


@pytest.fixture
def mock_service(monkeypatch: pytest.MonkeyPatch, indexed_dir: Path) -> None:
    from app.agents.tools import papervault_search_tool, papervault_stats_tool
    from app.services import papervault as papervault_module
    from app.services.papervault import PaperVaultService

    def _fake_get_service() -> PaperVaultService:
        svc = object.__new__(PaperVaultService)
        svc._base_dir_cache = {"test_user": indexed_dir}
        return svc

    monkeypatch.setattr(papervault_module, "get_papervault_service", _fake_get_service)
    monkeypatch.setattr(papervault_search_tool, "get_papervault_service", _fake_get_service)
    monkeypatch.setattr(papervault_stats_tool, "get_papervault_service", _fake_get_service)


async def test_papervault_search_returns_markdown(
    mock_service: None, indexed_dir: Path
) -> None:
    tool = PaperVaultSearch()
    result = await tool.invoke({"user_id": "test_user"}, query="federated")
    assert not result.is_error
    assert "ICML2024" in result.content
    assert "NeurIPS2023" in result.content
    assert "|" in result.content  # Markdown 表格


async def test_papervault_search_with_conf_filter(
    mock_service: None, indexed_dir: Path
) -> None:
    tool = PaperVaultSearch()
    result = await tool.invoke({"user_id": "test_user"}, query="federated", conf="ICML")
    assert not result.is_error
    assert "ICML2024" in result.content
    assert "NeurIPS2023" not in result.content


async def test_papervault_search_missing_user_id(
    mock_service: None, indexed_dir: Path
) -> None:
    tool = PaperVaultSearch()
    result = await tool.invoke({}, query="federated")
    assert result.is_error
    assert "user_id" in result.content


async def test_papervault_stats_returns_summary(
    mock_service: None, indexed_dir: Path
) -> None:
    tool = PaperVaultStats()
    result = await tool.invoke({"user_id": "test_user"})
    assert not result.is_error
    assert "论文总数" in result.content
    assert "2" in result.content
