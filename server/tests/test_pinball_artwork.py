import asyncio
import io
import sqlite3
import time
import zipfile

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from app.artwork_catalogs import LaunchBoxCatalog
from app.main import create_app
from app.thumbnails import LibretroThumbnails


def image():
    output = io.BytesIO()
    Image.new('RGB', (20, 30), 'green').save(output, 'PNG')
    return output.getvalue()


def catalog_archive(catalog):
    catalog.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(catalog.archive, 'w') as archive:
        archive.writestr('Metadata.xml', '''<LaunchBox>
          <Game><DatabaseID>1</DatabaseID><Name>Attack from Mars</Name><Platform>Pinball</Platform></Game>
          <Game><DatabaseID>2</DatabaseID><Name>Capture Only</Name><Platform>Pinball</Platform></Game>
          <GameImage><DatabaseID>1</DatabaseID><FileName>r2_flyer.jpg</FileName><Type>Advertisement Flyer - Front</Type></GameImage>
          <GameImage><DatabaseID>1</DatabaseID><FileName>cabinet.png</FileName><Type>Arcade - Cabinet</Type></GameImage>
          <GameImage><DatabaseID>1</DatabaseID><FileName>back.jpg</FileName><Type>Advertisement Flyer - Back</Type></GameImage>
          <GameImage><DatabaseID>1</DatabaseID><FileName>../escape.jpg</FileName><Type>Advertisement Flyer - Front</Type></GameImage>
          <GameImage><DatabaseID>1</DatabaseID><FileName>a_missing.png</FileName><Type>Screenshot - Gameplay</Type></GameImage>
          <GameImage><DatabaseID>1</DatabaseID><FileName>r2_gameplay.jpg</FileName><Type>Screenshot - Gameplay</Type></GameImage>
          <GameImage><DatabaseID>1</DatabaseID><FileName>z_duplicate.png</FileName><Type>Screenshot - Gameplay</Type></GameImage>
          <GameImage><DatabaseID>2</DatabaseID><FileName>only.png</FileName><Type>Screenshot - Gameplay</Type></GameImage>
        </LaunchBox>''')


def mock_images(monkeypatch):
    original = httpx.AsyncClient
    requested = []
    def respond(request):
        requested.append(request.url.path)
        return httpx.Response(404) if 'missing' in request.url.path else httpx.Response(200, content=image())
    monkeypatch.setattr('app.artwork_catalogs.httpx.AsyncClient', lambda **kwargs:
        original(transport=httpx.MockTransport(respond), **kwargs))
    return requested


def test_v2_catalog_migrates_to_pinball_flyers_and_gameplay(tmp_path, monkeypatch):
    catalog = LaunchBoxCatalog(tmp_path)
    catalog_archive(catalog)
    catalog.folder.mkdir(parents=True)
    with sqlite3.connect(catalog.database) as db:
        db.executescript('''CREATE TABLE games(id TEXT, system INTEGER, title TEXT);
            CREATE TABLE titles(game TEXT, system INTEGER, title TEXT, key TEXT, compact TEXT);
            CREATE TABLE images(game TEXT, file TEXT, priority INTEGER, region INTEGER);
            PRAGMA user_version=2;''')
    db.close()
    requests = mock_images(monkeypatch)
    async def scenario():
        results = await catalog.search('Attack from Mars (Bally 1995)', 10001)
        assert results[0]['id'] == '1'
        assert (await catalog.cover('1', 10001))[0]['provider'] == 'launchbox'
        assert requests == ['/r2_flyer.jpg']
        captures = await catalog.screenshots('Attack from Mars', 10001)
        assert len(captures) == 1 and captures[0]['provider'] == 'launchbox'
        assert 'gameplay' in captures[0]['source_id']
        assert await catalog.search('Capture Only', 10001) == []
        assert len(await catalog.screenshots('Capture Only', 10001)) == 1
        assert await catalog.screenshots('Attack from Mars 2', 10001) == []
        assert await catalog.search('Attack from Mars', 75) == []
    asyncio.run(scenario())
    with sqlite3.connect(catalog.database) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 3
        assert db.execute('SELECT file FROM images ORDER BY priority').fetchall() == [('r2_flyer.jpg',), ('cabinet.png',)]
    catalog.archive.unlink()
    assert asyncio.run(LaunchBoxCatalog(tmp_path).search('Attack from Mars', 10001))


def test_pinball_api_finds_covers_and_refreshes_old_empty_screenshot_cache(tmp_path, monkeypatch):
    app = create_app(tmp_path/'roms', tmp_path/'data', tmp_path/'media', token='token')
    catalog_archive(app.state.scraper.sources['launchbox'])
    mock_images(monkeypatch)
    library = app.state.library
    with TestClient(app, headers={'Authorization': 'Bearer token'}) as client:
        (library.roms/'vpinball').mkdir()
        (library.roms/'vpinball'/'Attack from Mars (Bally 1995).vpx').write_bytes(b'metadata-only-fixture')
        library.scan()
        game = library.games()[0]
        library.save_setting(f'screenshots:{game["id"]}', {'title': game['title'], 'time': time.time()})
        prefix = f'/api/games/{game["id"]}'
        results = client.get(prefix+'/scrape').json()
        assert results[0]['id'] == 'launchbox-1'
        assert client.post(prefix+'/scrape', json={'provider_id': results[0]['id']}).status_code == 200
        assert client.get(prefix+'/cover').status_code == 200
        assert not client.get(prefix+'/screenshots').json()['checked']
        refreshed = client.post(prefix+'/screenshots/refresh')
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()['checked']
        captures = refreshed.json()['images']
        assert len(captures) == 1 and captures[0]['provider'] == 'launchbox'
        assert client.get(captures[0]['url']).headers['content-type'] == 'image/jpeg'
        assert len(client.post(prefix+'/screenshots/refresh').json()['images']) == 1
        assert client.post(prefix+'/screenshots/refresh', headers={'Authorization': ''}).status_code == 401


def test_pinball_queries_strip_table_authors_without_losing_title_numbers(tmp_path):
    thumbnails = LibretroThumbnails(tmp_path)
    assert thumbnails.query('Attack from Mars (Bally 1995) g5k 1.3.11.vpx', 10001) == 'Attack from Mars'
    assert thumbnails.query('Medieval Madness VPW v1.0.1', 10001) == 'Medieval Madness'
    assert thumbnails.query('Black Knight 2000 (Williams 1989).vpxz', 10001) == 'Black Knight 2000'
