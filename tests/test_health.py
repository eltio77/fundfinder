from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from fundfinder.db import get_client
from fundfinder.main import create_app


class FakeAdmin:
    def __init__(self, fail: bool):
        self.fail = fail

    async def command(self, name: str):
        if self.fail:
            raise ServerSelectionTimeoutError("no servers")
        return {"ok": 1}


class FakeClient:
    def __init__(self, fail: bool = False):
        self.admin = FakeAdmin(fail)


def _client_with(fake: FakeClient) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_client] = lambda: fake
    return TestClient(app)


def test_health_ok():
    with _client_with(FakeClient()) as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mongo": "ok"}


def test_health_mongo_down_returns_503():
    with _client_with(FakeClient(fail=True)) as c:
        r = c.get("/health")
    assert r.status_code == 503
    assert r.json()["mongo"] == "unreachable"
