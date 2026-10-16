import asyncio
import io
import zipfile
import sqlite3
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.artwork import ArtworkChain
from app.artwork_catalogs import LaunchBoxCatalog, GameTDBCatalog
from app.main import create_app
from app.scraper import ScraperError
from app.thumbnails import LibretroThumbnails


def picture():
    buffer = io.BytesIO()
    Image.new('RGB', (16, 16), 'red').save(buffer, 'PNG')
    return buffer.getvalue()


def chain(tmp_path, results, broken=(), offline=()):
    calls = []
    matching = LibretroThumbnails(tmp_path)
    sources = []
    for name in ('libretro', 'launchbox', 'gametdb'):
        async def search(title, system, _name=name, **kwargs):
            calls.append(('search', _name))
            if _name in offline: raise ScraperError('Offline '+_name, stop_batch=True)
            return results.get(_name, [])
        async def cover(id, system, _name=name):
            calls.append(('cover', _name))
            if _name in broken: raise ScraperError('Imagen ausente')
            return {'title': 'Example', 'description': ''}, picture()
        async def title(id, system): return 'Example'
        sources.append(SimpleNamespace(search=search, cover=cover, title=title,
            query=matching.query, auto_candidate=matching.auto_candidate))
    return ArtworkChain(*sources), calls


@pytest.mark.parametrize('winner', ['libretro', 'launchbox', 'gametdb', None])
def test_priority_stops_at_first_compatible_source(tmp_path, winner):
    result = [{'id': '1', 'title': 'Example', 'description': 'Carátula'}]
    scraper, calls = chain(tmp_path, {winner: result} if winner else {})
    found = asyncio.run(scraper.search('Example', 3))
    expected = ['libretro', 'launchbox', 'gametdb']
    if winner:
        assert found[0]['provider'] == winner
        assert found[0]['id'] == winner+'-1'
        expected = expected[:expected.index(winner)+1]
    else:
        assert found == []
        assert asyncio.run(scraper.resolve('Example', 3)) is None
        calls = calls[:3]
    assert calls == [('search', name) for name in expected]


def test_bulk_resolve_falls_back_if_first_image_cannot_be_downloaded(tmp_path):
    result = [{'id': '1', 'title': 'Example', 'description': 'Carátula'}]
    scraper, calls = chain(tmp_path, {'libretro': result, 'launchbox': result}, broken={'libretro'})
    metadata, raw = asyncio.run(scraper.resolve('Example', 3))
    assert metadata['provider'] == 'launchbox' and raw == picture()
    assert calls == [('search', 'libretro'), ('cover', 'libretro'), ('search', 'launchbox'), ('cover', 'launchbox')]


def test_selected_image_fallback_and_legacy_ids(tmp_path):
    result = [{'id': '2', 'title': 'Example', 'description': 'Carátula'}]
    scraper, calls = chain(tmp_path, {'gametdb': result}, broken={'libretro', 'launchbox'})
    metadata, _ = asyncio.run(scraper.cover('oldlibretroid', 16))
    assert metadata['provider'] == 'gametdb'
    assert calls[0] == ('cover', 'libretro')


def test_unrelated_results_do_not_prevent_a_later_exact_match(tmp_path):
    scraper, calls = chain(tmp_path, {
        'libretro': [{'id': '2', 'title': 'Example 2', 'description': 'Carátula'}],
        'launchbox': [{'id': '1', 'title': 'Canonical', 'match_title': 'Example', 'description': 'Carátula'}]})
    result = asyncio.run(scraper.search('Example', 3))
    assert result[0]['provider'] == 'launchbox'
    assert scraper.auto_candidate('Example', result, 3)['title'] == 'Canonical'


def test_network_failure_does_not_block_other_sources_but_can_pause_batch(tmp_path):
    result = [{'id': '1', 'title': 'Example', 'description': 'Carátula'}]
    scraper, _ = chain(tmp_path, {'gametdb': result}, offline={'libretro', 'launchbox'})
    assert asyncio.run(scraper.resolve('Example', 16))[0]['provider'] == 'gametdb'
    scraper, _ = chain(tmp_path, {}, offline={'libretro', 'launchbox', 'gametdb'})
    with pytest.raises(ScraperError) as error: asyncio.run(scraper.resolve('Example', 16))
    assert error.value.stop_batch


def archive(catalog, xml):
    catalog.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(catalog.archive, 'w') as zipped:
        zipped.writestr('Metadata.xml' if catalog.name == 'launchbox' else 'wiitdb.xml', xml)


def test_catalog_repairs_incomplete_sqlite_and_corrupt_archive(tmp_path, monkeypatch):
    catalog = LaunchBoxCatalog(tmp_path)
    xml = '<LaunchBox><Game><DatabaseID>1</DatabaseID><Name>Example</Name><Platform>Nintendo Entertainment System</Platform></Game><GameImage><DatabaseID>1</DatabaseID><FileName>front.jpg</FileName><Type>Box - Front</Type></GameImage></LaunchBox>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zipped: zipped.writestr('Metadata.xml', xml)
    catalog.folder.mkdir(parents=True)
    db = sqlite3.connect(catalog.database)
    db.execute('PRAGMA user_version=1'); db.close()
    catalog.archive.parent.mkdir(parents=True)
    catalog.archive.write_bytes(b'incomplete-download')
    original = httpx.Client
    calls = []
    def respond(request):
        calls.append(request.url)
        return httpx.Response(200, content=buffer.getvalue())
    monkeypatch.setattr('app.artwork_catalogs.httpx.Client', lambda **kwargs:
        original(transport=httpx.MockTransport(respond), **kwargs))
    assert asyncio.run(catalog.search('Example', 3))[0]['id'] == '1'
    assert len(calls) == 1


def test_launchbox_index_keeps_platform_alias_and_front_art_only(tmp_path, monkeypatch):
    catalog = LaunchBoxCatalog(tmp_path)
    archive(catalog, '''<LaunchBox>
      <Game><DatabaseID>1</DatabaseID><Name>Example</Name><Platform>Nintendo Entertainment System</Platform></Game>
      <Game><DatabaseID>2</DatabaseID><Name>Other</Name><Platform>Windows</Platform></Game>
      <GameAlternateName><DatabaseID>1</DatabaseID><AlternateName>Ejemplo</AlternateName></GameAlternateName>
      <GameImage><DatabaseID>1</DatabaseID><FileName>front.jpg</FileName><Type>Box - Front</Type><Region>Spain</Region></GameImage>
      <GameImage><DatabaseID>1</DatabaseID><FileName>back.jpg</FileName><Type>Box - Back</Type></GameImage>
    </LaunchBox>''')
    calls = []
    original = httpx.AsyncClient
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=picture())
    monkeypatch.setattr('app.artwork_catalogs.httpx.AsyncClient', lambda **kwargs:
        original(transport=httpx.MockTransport(respond), **kwargs))
    async def scenario():
        result = await catalog.search('Ejemplo', 3)
        assert result[0]['title'] == 'Example' and result[0]['match_title'] == 'Ejemplo'
        assert await catalog.search('Example', 26) == []
        assert (await catalog.cover('1', 3))[0]['provider'] == 'launchbox'
        assert await catalog.title('1', 26) is None
    asyncio.run(scenario())
    assert calls == ['https://images.launchbox-app.com/front.jpg']
    # El índice persiste y no requiere volver a descargar ni tener el XML a mano.
    catalog.archive.unlink()
    assert asyncio.run(LaunchBoxCatalog(tmp_path).search('Example', 3))


def test_gametdb_distinguishes_gamecube_and_wii_and_tries_other_cover_language(tmp_path, monkeypatch):
    catalog = GameTDBCatalog(tmp_path, 'wii')
    archive(catalog, '''<datafile>
      <game name="Example"><id>REXP01</id><type>Wii</type><region>PAL</region>
        <locale lang="EN"><title>Example</title></locale><locale lang="ES"><title>Ejemplo</title></locale></game>
      <game name="Cube"><id>GCBE01</id><type>GameCube</type><region>NTSC-U</region>
        <locale lang="EN"><title>Cube</title></locale></game>
    </datafile>''')
    calls = []
    original = httpx.AsyncClient
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(404) if '/ES/' in request.url.path else httpx.Response(200, content=picture())
    monkeypatch.setattr('app.artwork_catalogs.httpx.AsyncClient', lambda **kwargs:
        original(transport=httpx.MockTransport(respond), **kwargs))
    async def scenario():
        assert (await catalog.search('Ejemplo', 16))[0]['id'] == 'REXP01'
        assert await catalog.search('Cube', 16) == []
        assert (await catalog.search('Cube', 13))[0]['id'] == 'GCBE01'
        assert (await catalog.cover('REXP01', 16))[0]['provider'] == 'gametdb'
    asyncio.run(scenario())
    assert calls == ['https://art.gametdb.com/wii/cover/ES/REXP01.png', 'https://art.gametdb.com/wii/cover/EN/REXP01.png']


def test_api_legacy_provider_uses_chain_and_records_actual_image_source(tmp_path, monkeypatch):
    app = create_app(tmp_path/'roms', tmp_path/'data', tmp_path/'media', token='')
    scraper, calls = chain(tmp_path, {'launchbox': [{'id': '1', 'title': 'Example', 'description': 'Carátula'}]})
    app.state.scraper.sources = scraper.sources
    app.state.scraper.libretro = scraper.libretro
    with TestClient(app) as client:
        client.post('/api/systems/nes/upload', files={'file': ('Example.nes', b'fixture')})
        game = client.get('/api/games').json()[0]
        result = client.get(f'/api/games/{game["id"]}/scrape?provider=libretro').json()
        assert result[0]['provider'] == 'launchbox'
        applied = client.post(f'/api/games/{game["id"]}/scrape', json={'provider': 'libretro', 'provider_id': result[0]['id']})
        assert applied.status_code == 200
        assert applied.json()['provider'] == 'launchbox'
        assert client.post(f'/api/games/{game["id"]}/cover', files={'file': ('manual.png', picture())}).status_code == 200
        assert client.get('/api/games').json()[0]['provider'] == 'manual'


def test_bulk_uses_download_fallback_and_keeps_existing_manual_art(tmp_path):
    app = create_app(tmp_path/'roms', tmp_path/'data', tmp_path/'media', token='')
    library = app.state.library
    folder = library.roms/'nes'; folder.mkdir()
    for name in ('Example', 'Manual'): (folder/f'{name}.nes').write_bytes(b'fixture')
    library.scan()
    manual = next(game for game in library.games() if game['title'] == 'Manual')
    library.update(manual['id'], cover='existing.jpg', provider='manual')
    scraper, calls = chain(tmp_path, {'launchbox': [{'id': '1', 'title': 'Example', 'description': 'Carátula'}]})
    app.state.scraper.sources, app.state.scraper.libretro = scraper.sources, scraper.libretro
    async def scenario():
        await app.state.bulk.start()
        await app.state.bulk.task
    asyncio.run(scenario())
    state = app.state.bulk.public()
    assert state['updated'] == 1 and state['already_covered'] == 1
    assert 'launchbox' in state['recent'][0]['message']
    assert library.game(manual['id'])['cover'] == 'existing.jpg'
    assert library.game(manual['id'])['provider'] == 'manual'


def test_invalid_image_does_not_count_as_success(tmp_path):
    result = [{'id': '1', 'title': 'Example', 'description': 'Carátula'}]
    scraper, _ = chain(tmp_path, {'libretro': result, 'launchbox': result})
    async def invalid(*args): return {'title': 'Example'}, b'<html>not an image</html>'
    scraper.sources['libretro'].cover = invalid
    assert asyncio.run(scraper.resolve('Example', 3))[0]['provider'] == 'launchbox'


def test_image_server_outage_does_not_retry_every_image(tmp_path, monkeypatch):
    catalog = LaunchBoxCatalog(tmp_path)
    archive(catalog, '''<LaunchBox>
      <Game><DatabaseID>1</DatabaseID><Name>Example</Name><Platform>Nintendo Entertainment System</Platform></Game>
      <GameImage><DatabaseID>1</DatabaseID><FileName>one.jpg</FileName><Type>Box - Front</Type></GameImage>
      <GameImage><DatabaseID>1</DatabaseID><FileName>two.jpg</FileName><Type>Box - Front</Type></GameImage>
    </LaunchBox>''')
    calls = []
    original = httpx.AsyncClient
    def respond(request):
        calls.append(request.url)
        raise httpx.ConnectError('Offline', request=request)
    monkeypatch.setattr('app.artwork_catalogs.httpx.AsyncClient', lambda **kwargs:
        original(transport=httpx.MockTransport(respond), **kwargs))
    with pytest.raises(ScraperError) as error: asyncio.run(catalog.cover('1', 3))
    assert error.value.stop_batch and len(calls) == 1
