import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "roms", tmp_path / "data", tmp_path / "media", token="test-token")
    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as client:
        yield client


def test_empty_library_and_auth(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/systems", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/systems").json() == []
    systems = client.get("/api/systems?include_empty=true").json()
    assert len(systems) == 19
    assert "dreamcast" not in {s["id"] for s in systems}
    assert not (client.app.state.library.roms / "dreamcast").exists()


def test_upload_scan_download_and_persistence(client):
    payload = b"test-rom-content"
    response = client.post("/api/systems/gba/upload", files={"file": ("Test (Europe).gba", payload)})
    assert response.status_code == 201
    systems = client.get("/api/systems").json()
    assert systems[0]["id"] == "gba" and systems[0]["game_count"] == 1
    game = client.get("/api/games?system_id=gba").json()[0]
    assert game["title"] == "Test"
    assert client.get(f"/api/games/{game['id']}/download").content == payload
    assert client.patch(f"/api/games/{game['id']}", json={"favorite": True, "title": "Mi juego"}).status_code == 200
    assert client.post("/api/scan").json()["game_count"] == 1
    assert client.get("/api/games?favorites=true&q=Mi").json()[0]["title"] == "Mi juego"
    duplicate = client.post("/api/systems/gba/upload", files={"file": ("Test (Europe).gba", b"other")})
    assert duplicate.status_code == 409
    assert client.get(f"/api/games/{game['id']}/download").content == payload
    library = client.app.state.library
    reopened = create_app(library.roms, library.data, library.media, token="test-token")
    with TestClient(reopened, headers={"Authorization": "Bearer test-token"}) as other:
        assert other.get("/api/games?favorites=true").json()[0]["title"] == "Mi juego"
    (library.roms / game["path"]).unlink()
    client.post("/api/scan")
    assert client.get("/api/games").json() == []


def test_equal_size_replacement_changes_revision_without_losing_metadata(client):
    import os
    client.post('/api/systems/nes/upload', files={'file': ('Example.nes', b'AAAA')})
    before = client.get('/api/games').json()[0]
    client.patch(f'/api/games/{before["id"]}', json={'favorite': True, 'title': 'Mi título'})
    path = client.app.state.library.roms/before['path']
    previous = path.stat().st_mtime_ns
    path.write_bytes(b'BBBB')
    os.utime(path, ns=(previous+1_000_000, previous+1_000_000))
    client.post('/api/scan')
    after = client.get('/api/games').json()[0]
    assert after['size'] == before['size'] and after['revision'] != before['revision']
    assert after['favorite'] and after['title'] == 'Mi título'
    assert client.get(f'/api/games/{after["id"]}/download').content == b'BBBB'


@pytest.mark.parametrize("filename,status", [("../escape.gba", 422), ("x\\escape.gba", 422),
                                             ("wrong.iso", 422), ("valid.gba", 201)])
def test_upload_validation(client, filename, status):
    assert client.post("/api/systems/gba/upload", files={"file": (filename, b"rom")}).status_code == status


def test_multidisc_tracks_not_duplicated(client):
    folder = client.app.state.library.roms / "psx"
    folder.mkdir()
    (folder / "Disc 1.bin").write_bytes(b"track")
    (folder / "Disc 2.bin").write_bytes(b"track")
    (folder / "Disc 1.cue").write_text('FILE "Disc 1.bin" BINARY\n', encoding="utf-8")
    (folder / "Disc 2.cue").write_text('FILE "Disc 2.bin" BINARY\n', encoding="utf-8")
    (folder / "Game.m3u").write_text("Disc 1.cue\nDisc 2.cue\n", encoding="utf-8")
    assert client.post("/api/scan").json()["game_count"] == 1
    assert client.get("/api/games").json()[0]["filename"] == "Game.m3u"


def test_manual_cover_and_invalid_image(client):
    client.post("/api/systems/gba/upload", files={"file": ("Game.gba", b"rom")})
    id = client.get("/api/games").json()[0]["id"]
    url = f"/api/games/{id}/cover"
    assert client.post(url, files={"file": ("bad.jpg", b"not-an-image")}).status_code == 422
    image = io.BytesIO()
    Image.new("RGB", (12, 12), "blue").save(image, "PNG")
    assert client.post(url, files={"file": ("cover.png", image.getvalue())}).status_code == 200
    result = client.get(url)
    assert result.status_code == 200 and result.headers["content-type"] == "image/jpeg"
    client.post("/api/scan")
    assert client.get("/api/games").json()[0]["provider"] == "manual"


def test_add_console_and_validate_identifier(client):
    assert client.post("/api/systems", json={"id": "../bad", "name": "Bad", "extensions": [".rom"]}).status_code == 422
    assert client.post("/api/systems", json={"id": "homebrew", "name": "Homebrew", "extensions": [".rom"]}).status_code == 201
    assert client.post("/api/systems/homebrew/upload", files={"file": ("Demo.rom", b"demo")}).status_code == 201
    assert client.post("/api/systems", json={"id": "homebrew", "name": "Homebrew", "extensions": [".rom"]}).status_code == 409


def test_only_account_free_providers_are_available(client):
    settings = client.get("/api/settings").json()
    assert settings["scrape_provider"] == "auto"
    assert settings["scrape_order"] == ["libretro", "launchbox", "gametdb"]
    assert all(not p["requires_key"] and not p["requires_account"] for p in settings["providers"])
    assert not any("screenscraper" in key for key in settings)
    assert client.put("/api/settings/screenscraper", json={"username": "unused"}).status_code == 404
    assert client.post("/api/settings/screenscraper/check").status_code == 404
    assert client.put("/api/settings/scrape", json={"provider": "screenscraper"}).status_code == 422


def test_scraper_candidates_and_apply(client, monkeypatch):
    client.post("/api/systems/gba/upload", files={"file": ("Game.gba", b"rom")})
    id = client.get("/api/games").json()[0]["id"]
    image = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(image, "PNG")

    async def search(title, system):
        assert title == "Game" and system == 12
        return [{"id": "123", "title": "Resultado", "description": "Descripción"}]

    async def cover(provider_id, system):
        assert provider_id == "123" and system == 12
        return {"title": "Resultado", "description": "Descripción"}, image.getvalue()

    monkeypatch.setattr(client.app.state.scraper, "search", search)
    monkeypatch.setattr(client.app.state.scraper, "cover", cover)
    assert client.get(f"/api/games/{id}/scrape").json()[0]["id"] == "123"
    result = client.post(f"/api/games/{id}/scrape", json={"provider_id": "123"})
    assert result.status_code == 200
    assert result.json()["provider"] == "libretro"
    assert client.get(result.json()["cover_url"]).status_code == 200


def test_migrate_old_systems_and_provider_without_losing_metadata(client):
    import json
    client.post("/api/systems/nes/upload", files={"file": ("Example.nes", b"cartridge")})
    game = client.get("/api/games").json()[0]
    library = client.app.state.library
    library.update(game["id"], cover="old.jpg", provider="screenscraper", description="Ficha existente")
    config = library.get_system("nes")
    config["screenscraper_id"] = config.pop("metadata_id")
    with library.connect() as db:
        db.execute("UPDATE systems SET config=? WHERE id='nes'", (json.dumps(config),))
    library.save_setting("screenscraper_account", {"password": "old-secret"})
    library.save_setting("screenscraper_developer", {"password": "old-dev-secret"})
    library.save_setting("scrape_provider", "screenscraper")
    app = create_app(library.roms, library.data, library.media, token="test-token")
    with TestClient(app, headers={"Authorization": "Bearer test-token"}) as reopened:
        assert reopened.get("/api/settings").json()["scrape_provider"] == "auto"
        assert app.state.library.get_system("nes")["metadata_id"] == 3
        assert app.state.library.setting("screenscraper_account") is None
        assert app.state.library.setting("screenscraper_developer") is None
        preserved = reopened.get("/api/games").json()[0]
        assert preserved["cover_url"] and preserved["description"] == "Ficha existente"
        assert preserved["provider"] == "screenscraper"
        assert reopened.get(f'/api/games/{game["id"]}/download').content == b"cartridge"
