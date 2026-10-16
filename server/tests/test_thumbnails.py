import asyncio
import io

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.thumbnails import ImageLinks, LibretroThumbnails


def test_public_index_filters_links_and_groups_regions(tmp_path):
    parser = ImageLinks()
    parser.feed('<a href="Mario%20Kart%20DS%20(Europe).png">x</a><a href="https://other/a.png">bad</a><a href="../bad.png">bad</a>')
    assert parser.names == {"Mario Kart DS (Europe).png"}
    provider = LibretroThumbnails(tmp_path)
    result = provider.auto_candidate("Mario Kart DS", [
        {"id": "eu", "title": "Mario Kart DS"}, {"id": "us", "title": "Mario Kart DS"}], 15)
    assert result["id"] == "eu"
    assert provider.auto_candidate("Mario Kart DS", [{"id": "bad", "title": "Mario Party DS"}], 15) is None


def test_public_scrape_works_without_keys_and_preserves_description(tmp_path, monkeypatch):
    original = httpx.AsyncClient
    image = io.BytesIO()
    Image.new("RGB", (16, 16), "blue").save(image, "PNG")
    requests = []

    def respond(request):
        requests.append(str(request.url))
        assert request.url.host == "thumbnails.libretro.com"
        if request.url.path.endswith("/"):
            return httpx.Response(200, text='<a href="Mario%20Kart%20DS%20(Europe)%20(Demo).png">demo</a><a href="Mario%20Kart%20DS%20(Europe).png">box</a>')
        return httpx.Response(200, content=image.getvalue())

    monkeypatch.setattr("app.thumbnails.httpx.AsyncClient", lambda **kwargs:
                        original(transport=httpx.MockTransport(respond), **kwargs))
    app = create_app(tmp_path / "roms", tmp_path / "data", tmp_path / "media", token="token")
    with TestClient(app, headers={"Authorization": "Bearer token"}) as client:
        client.post("/api/systems/nds/upload", files={"file": ("Mario Kart DS.nds", b"rom")})
        game = client.get("/api/games").json()[0]
        app.state.library.update(game["id"], description="Descripción previa")
        result = client.get(f"/api/games/{game['id']}/scrape?provider=libretro").json()
        assert result[0]["title"] == "Mario Kart DS"
        assert "Demo" not in result[0]["description"]
        cover = client.post(f"/api/games/{game['id']}/scrape", json={"provider":"libretro", "provider_id":result[0]["id"]})
        assert cover.status_code == 200
        assert cover.json()["provider"] == "libretro"
        assert cover.json()["description"] == "Descripción previa"
        assert client.get(cover.json()["cover_url"]).status_code == 200
        assert client.get(f"/api/games/{game['id']}/scrape?provider=unknown").status_code == 422
        assert client.put("/api/settings/scrape", json={"provider":"libretro"}).status_code == 200
    assert len(requests) == 2  # El índice se reutiliza al elegir la imagen.


def test_bulk_libretro_requires_no_credentials(tmp_path):
    app = create_app(tmp_path / "roms", tmp_path / "data", tmp_path / "media", token="")
    bulk = app.state.bulk
    async def scenario():
        await bulk.start(provider="libretro")
        await bulk.task
        assert bulk.public()["status"] == "completed"
        assert bulk.public()["provider"] == "libretro"
    asyncio.run(scenario())


@pytest.mark.parametrize('system,filename,title', [
    ('nes', '1942.NES', '1942'), ('nes', 'AirFortress.nes', 'Air Fortress'),
    ('nes', '8EYES.NES', '8 Eyes'), ('atari2600', 'Pac-Man (1982) (Atari) ~.bin', 'Pac-Man'),
])
def test_console_cover_lookup_uses_correct_catalog_and_normalizes_titles(tmp_path, monkeypatch, system, filename, title):
    from urllib.parse import quote
    original = httpx.AsyncClient
    requests = []
    def respond(request):
        requests.append(request)
        folder = 'Atari - 2600' if system == 'atari2600' else 'Nintendo - Nintendo Entertainment System'
        assert folder in request.url.path
        return httpx.Response(200, text=f'<a href="{quote(title)}%20(USA).png">image</a>')
    monkeypatch.setattr('app.thumbnails.httpx.AsyncClient', lambda **kwargs:
        original(transport=httpx.MockTransport(respond), **kwargs))
    app = create_app(tmp_path/'roms', tmp_path/'data', tmp_path/'media', token='')
    with TestClient(app) as client:
        assert client.post(f'/api/systems/{system}/upload', files={'file': (filename, b'fixture')}).status_code == 201
        game = client.get('/api/games').json()[0]
        response = client.get(f'/api/games/{game["id"]}/scrape')
        assert response.status_code == 200
        assert response.json()[0]['title'] == title
        assert app.state.scraper.auto_candidate(game['title'], response.json(), app.state.library.get_system(system)['metadata_id']) is not None
    assert len(requests) == 1


def test_compact_titles_do_not_match_wrong_sequels(tmp_path):
    provider = LibretroThumbnails(tmp_path)
    assert provider.auto_candidate('MarioBros2', [{'id': '3', 'title': 'Mario Bros 3'}], 3) is None
