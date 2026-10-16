import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.player import PlayerAssets


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "roms", tmp_path / "data", tmp_path / "media", token="token")
    with TestClient(app, headers={"Authorization": "Bearer token"}) as client:
        yield client


def test_integrated_systems_and_auth(client):
    assert client.get("/api/player", headers={"Authorization": ""}).status_code == 401
    data = client.get("/api/player").json()
    assert data["systems"]["nds"] == "desmume"
    assert data["systems"]["mame"] == "mame2003_plus"
    assert set(data["systems"]) == {"nds", "gb", "gbc", "gba", "snes", "n64", "mame"}


@pytest.mark.parametrize("path", ["../secret", "folder/../../file", "/absolute", "folder\\file", "https://other/file", ".env"])
def test_asset_paths_are_restricted(tmp_path, path):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        PlayerAssets(tmp_path).path(path)


def test_engine_download_is_pinned_cached_and_protected(client, monkeypatch):
    original = httpx.AsyncClient
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=b"engine-code")

    monkeypatch.setattr("app.player.httpx.AsyncClient", lambda **kwargs:
                        original(transport=httpx.MockTransport(respond), **kwargs))
    endpoint = "/api/player/assets/loader.js"
    assert client.get(endpoint, headers={"Authorization": ""}).status_code == 401
    assert client.get(endpoint).content == b"engine-code"
    assert client.get(endpoint).content == b"engine-code"
    assert requests == ["https://cdn.emulatorjs.org/4.2.3/data/loader.js"]
