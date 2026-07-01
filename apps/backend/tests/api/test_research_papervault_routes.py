"""PaperVault API 路由测试。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import research as research_routes
from app.core.auth import require_auth
from app.models.user import UserInfo
from app.services.papervault import (
    PaperVaultPaper,
    PaperVaultQuery,
    PaperVaultStats,
    PaperVaultStatusResponse,
    PaperVaultSyncResponse,
)


class _FakePapervaultService:
    def __init__(self) -> None:
        self.papers = [
            PaperVaultPaper(
                id="ICML2024:abc",
                conf="ICML2024",
                year=2024,
                title="Federated Learning for Vision",
                authors=["Alice", "Bob"],
                abstract="We study federated learning.",
                url="http://example.com/1",
                code_url="https://github.com/foo/bar",
                has_code=True,
            ),
            PaperVaultPaper(
                id="NeurIPS2023:def",
                conf="NeurIPS2023",
                year=2023,
                title="Federated Optimization",
                authors=["Carol"],
                abstract="Optimization in federated settings.",
                url="http://example.com/2",
                code_url=None,
                has_code=False,
            ),
        ]

    def status(self, user_id: str) -> PaperVaultStatusResponse:
        return PaperVaultStatusResponse(
            ready=True,
            downloaded=True,
            indexed=True,
            total=2,
            version="etag-123",
            remote_version="etag-123",
            updated_at="2024-01-01T00:00:00Z",
            needs_sync=False,
        )

    def sync(self, user_id: str, *, force: bool = False) -> PaperVaultSyncResponse:
        return PaperVaultSyncResponse(
            success=True,
            downloaded=False,
            indexed=False,
            total=2,
            version="etag-123",
            message="已是最新",
        )

    def search(self, user_id: str, query: PaperVaultQuery) -> tuple[list[PaperVaultPaper], int]:
        filtered = [p for p in self.papers if self._matches(p, query)]
        return filtered, len(filtered)

    def stats(
        self, user_id: str, *, conf: list[str] | None = None, since: int | None = None, until: int | None = None
    ) -> PaperVaultStats:
        return PaperVaultStats(
            total=2,
            with_abstract=2,
            with_code=1,
            yearly={2024: 1, 2023: 1},
            confs={"ICML2024": 1, "NeurIPS2023": 1},
        )

    def list_confs(self, user_id: str) -> list[str]:
        return ["ICML2024", "NeurIPS2023"]

    @staticmethod
    def _matches(paper: PaperVaultPaper, query: PaperVaultQuery) -> bool:
        if query.conf and paper.conf not in query.conf:
            return False
        if query.has_code is not None and paper.has_code != query.has_code:
            return False
        if query.since is not None and paper.year < query.since:
            return False
        if query.until is not None and paper.year > query.until:
            return False
        return True


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        research_routes.papervault,
        "get_papervault_service",
        lambda: _FakePapervaultService(),
    )

    app = FastAPI()
    app.include_router(research_routes.router)
    app.dependency_overrides[require_auth()] = lambda: UserInfo(
        user_id="test_user", role="user", auth_provider="local"
    )
    return TestClient(app)


def test_get_status(client: TestClient) -> None:
    response = client.get("/research/papervault/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["total"] == 2


def test_post_sync(client: TestClient) -> None:
    response = client.post("/research/papervault/sync")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_search_papers(client: TestClient) -> None:
    response = client.get("/research/papervault/papers?query=federated&conf=ICML2024")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["papers"]) == 1
    assert data["papers"][0]["conf"] == "ICML2024"


def test_search_papers_with_has_code(client: TestClient) -> None:
    response = client.get("/research/papervault/papers?has_code=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["papers"][0]["has_code"] is True


def test_list_confs(client: TestClient) -> None:
    response = client.get("/research/papervault/confs")
    assert response.status_code == 200
    data = response.json()
    assert "ICML2024" in data


def test_get_stats(client: TestClient) -> None:
    response = client.get("/research/papervault/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["with_code"] == 1
