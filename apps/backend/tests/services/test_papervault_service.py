"""PaperVault 服务层测试。"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from app.services.papervault.dataset_service import PaperVaultDatasetService
from app.services.papervault.index_service import PaperVaultIndexService
from app.services.papervault.models import PaperVaultQuery
from app.services.papervault.query_service import PaperVaultQueryService

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
    {
        "conf": "ICML2023",
        "paper_name": "Deep Learning Basics",
        "paper_authors": ["Dave Lee"],
        "paper_url": "http://example.com/3",
        "paper_abstract": "Introduction to deep learning.",
        "paper_code": "#",
    },
]


def _write_sample_cache(base_dir: Path) -> Path:
    cache_path = base_dir / "cache.jsonl.gz"
    with gzip.open(cache_path, "wt", encoding="utf-8") as fh:
        for paper in SAMPLE_PAPERS:
            fh.write(json.dumps(paper) + "\n")
    return cache_path


@pytest.fixture
def sample_base(tmp_path: Path) -> Path:
    base = tmp_path / "papervault"
    base.mkdir(parents=True)
    _write_sample_cache(base)
    return base


def test_index_service_builds_and_counts(sample_base: Path) -> None:
    service = PaperVaultIndexService(sample_base)
    result = service.build(force=True)
    assert result["success"] is True
    assert result["total"] == len(SAMPLE_PAPERS)

    status = service.status()
    assert status["ready"] is True
    assert status["total"] == len(SAMPLE_PAPERS)


def test_query_service_search_all(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    papers, total = query.search(PaperVaultQuery())
    assert total == len(SAMPLE_PAPERS)
    assert len(papers) == len(SAMPLE_PAPERS)


def test_query_service_search_by_keyword(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    papers, total = query.search(PaperVaultQuery(query="federated"))
    assert total == 2
    assert all("federated" in (p.title + (p.abstract or "")).lower() for p in papers)


def test_query_service_search_by_title(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    papers, total = query.search(PaperVaultQuery(query="vision", field="title"))
    assert total == 1
    assert papers[0].title == "Federated Learning for Vision"


def test_query_service_search_by_author(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    papers, total = query.search(PaperVaultQuery(query="Carol", field="author"))
    assert total == 1
    assert "Carol White" in papers[0].authors


def test_query_service_conf_prefix_filter(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    papers, total = query.search(PaperVaultQuery(conf=["ICML"]))
    assert total == 2
    assert all(p.conf.startswith("ICML") for p in papers)


def test_query_service_conf_exact_filter(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    papers, total = query.search(PaperVaultQuery(conf=["ICML2024"]))
    assert total == 1
    assert papers[0].conf == "ICML2024"


def test_query_service_year_filter(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    papers, total = query.search(PaperVaultQuery(since=2024, until=2024))
    assert total == 1
    assert papers[0].year == 2024


def test_query_service_has_code_filter(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    papers, total = query.search(PaperVaultQuery(has_code=True))
    assert total == 1
    assert papers[0].has_code is True


def test_query_service_sort(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    papers, _ = query.search(PaperVaultQuery(sort="year"))
    years = [p.year for p in papers]
    assert years == sorted(years)

    papers, _ = query.search(PaperVaultQuery(sort="-year"))
    years = [p.year for p in papers]
    assert years == sorted(years, reverse=True)


def test_query_service_stats(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    stats = query.stats()
    assert stats.total == len(SAMPLE_PAPERS)
    assert stats.with_abstract == 3
    assert stats.with_code == 1
    assert 2023 in stats.yearly
    assert 2024 in stats.yearly


def test_query_service_stats_with_conf_filter(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    stats = query.stats(conf=["ICML"])
    assert stats.total == 2


def test_query_service_list_confs(sample_base: Path) -> None:
    PaperVaultIndexService(sample_base).build(force=True)
    query = PaperVaultQueryService(sample_base)

    confs = query.list_confs()
    assert set(confs) == {"ICML2024", "NeurIPS2023", "ICML2023"}


def test_dataset_service_status_not_downloaded(tmp_path: Path) -> None:
    service = PaperVaultDatasetService(tmp_path / "papervault")
    status = service.status()
    assert status["ready"] is False
    assert status["downloaded"] is False
    assert status["indexed"] is False


def test_dataset_service_validate_cache_file(sample_base: Path) -> None:
    service = PaperVaultDatasetService(sample_base)
    service._validate_cache_file()  # 不应抛异常

    bad_dir = sample_base / "bad"
    bad_dir.mkdir()
    bad_cache = bad_dir / "cache.jsonl.gz"
    with gzip.open(bad_cache, "wt", encoding="utf-8") as fh:
        fh.write("not json\n")
    service_bad = PaperVaultDatasetService(bad_dir)
    with pytest.raises(ValueError):
        service_bad._validate_cache_file()
