import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    folder = tmp_path / "roms" / "mame"
    folder.mkdir(parents=True)
    (folder / "game.zip").write_bytes(b"main-rom")
    (folder / "bios.zip").write_bytes(b"bios-rom")
    (folder / "game").mkdir()
    (folder / "game" / "disk.chd").write_bytes(b"disk-content")
    app = create_app(tmp_path / "roms", tmp_path / "data", tmp_path / "media", token="token")
    with TestClient(app, headers={"Authorization": "Bearer token"}) as client:
        yield client


def test_mame_manifest_downloads_dependencies_without_duplicate_disk_game(client):
    games = client.get("/api/games?system_id=mame").json()
    assert len(games) == 2
    game = next(g for g in games if g["filename"] == "game.zip")
    response = client.post(f"/api/games/{game['id']}/mame-assets", json={
        "files": ["game.zip", "bios.zip", "game/disk.chd", "missing.zip"]})
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["primary"] == "game.zip"
    assert [f["path"] for f in manifest["files"]] == ["game.zip", "bios.zip", "game/disk.chd"]
    assert manifest["missing"] == ["missing.zip"]
    assert client.get(manifest["files"][2]["url"]).content == b"disk-content"
    assert client.get(manifest["files"][1]["url"]).content == b"bios-rom"
    assert client.get("/api/mame/download?path=bios.zip", headers={"Authorization": ""}).status_code == 401


@pytest.mark.parametrize("path", ["../gba/game.zip", "/etc/passwd", "C:/file.zip", "folder\\file.zip", "folder/../file.zip", "folder/.hidden.ini"])
def test_mame_assets_reject_unsafe_paths(client, path):
    assert client.get("/api/mame/download", params={"path": path}).status_code == 422


def test_mame_manifest_requires_mame_game_and_handles_missing(client):
    client.post("/api/systems/gba/upload", files={"file": ("other.gba", b"rom")})
    id = client.get("/api/games?system_id=gba").json()[0]["id"]
    assert client.post(f"/api/games/{id}/mame-assets", json={}).status_code == 422
    assert client.get("/api/mame/download?path=missing.zip").status_code == 404
