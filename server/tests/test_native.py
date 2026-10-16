import asyncio
import hashlib
import zipfile
import zlib

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.arcade import ArcadeCatalog
from app.arcade import ArcadeSelector
from app.library import Library
from app.main import create_app
from app.native import HistoricalMameCatalog, NativeAssets, BowlingAudioCatalog


def test_bowling_profile_does_not_weaken_other_catalogs_or_accept_missing_chips(tmp_path):
    library=Library(tmp_path/'roms',tmp_path/'data',tmp_path/'media')
    assert 'mame2010' not in ArcadeSelector(library).catalogs
    assert 'mame2010' not in ArcadeSelector(library,native=True).catalogs
    core=BowlingAudioCatalog(library)
    catalog=asyncio.run(core.load())
    assert set(catalog)=={'wcbowl'}
    assert len(catalog['wcbowl']['roms'])==17
    (library.roms/'mame').mkdir()
    with zipfile.ZipFile(library.roms/'mame/wcbowl.zip','w') as archive:archive.writestr('wrong.bin',b'wrong')
    with pytest.raises(HTTPException):core.plan({'path':'mame/wcbowl.zip'},catalog)


@pytest.mark.parametrize("matching", [True, False])
def test_bowling_fallback_is_native_only_and_requires_matching_chips(tmp_path, monkeypatch, matching):
    chip = b"test-bowling-program" * 256
    crc = f"{zlib.crc32(chip):08x}"
    profile = ArcadeCatalog.parse(f'<mame><game name="wcbowl"><rom name="chip.bin" size="{len(chip)}" crc="{crc}"/></game></mame>')

    async def empty_catalog(self):
        return {}

    async def bowling_catalog(self):
        return profile

    monkeypatch.setattr(ArcadeCatalog, "load", empty_catalog)
    monkeypatch.setattr(HistoricalMameCatalog, "load", empty_catalog)
    monkeypatch.setattr(BowlingAudioCatalog, "load", bowling_catalog)
    monkeypatch.setattr("app.main.mame_web_plan", lambda library, game: None)
    app = create_app(tmp_path / "roms", tmp_path / "data", tmp_path / "media", token="")
    folder = tmp_path / "roms/mame"
    folder.mkdir()
    with zipfile.ZipFile(folder / "wcbowl.zip", "w") as archive:
        archive.writestr("chip.bin", chip if matching else b"incompatible-program")
    with TestClient(app) as client:
        game = next(game for game in client.get("/api/games").json() if game["filename"] == "wcbowl.zip")
        endpoint = f'/api/games/{game["id"]}/arcade/cores'
        assert client.get(endpoint).json()["candidates"] == []
        response = client.get(endpoint, params={"native": True, "identify": True})
        assert response.status_code == 200
        result = response.json()
        if matching:
            plan, = result["candidates"]
            assert plan["core"] == "mame2003_plus"
            assert plan["engine"] == "native"
            assert plan["compatibility_profile"] == "wcbowl-166-audio"
            assert plan["files"][0]["destination"] == "wcbowl.zip"
            assert not any(item["core"] == "mame2003_plus" for item in result["rejected"])
        else:
            assert result["candidates"] == []
            assert any(item["core"] == "mame2003_plus" for item in result["rejected"])


def test_native_assets_verify_download_and_cache_and_reject_unknown_core(tmp_path, monkeypatch):
    original = httpx.AsyncClient
    binary = b"native-engine-test"
    requests = []
    def respond(request):
        requests.append(request.url)
        return httpx.Response(200, content=binary)
    monkeypatch.setattr("app.native.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    assets = NativeAssets(tmp_path)
    assets.metadata = {"test": {"mame": {"source": "https://example.test/engine.zip", "size": len(binary), "sha256": hashlib.sha256(binary).hexdigest()}}}
    async def run():
        assert (await assets.get("test", "mame")).read_bytes() == binary
        assert (await assets.get("test", "mame")).read_bytes() == binary
        with pytest.raises(HTTPException) as error:
            await assets.get("../test", "mame")
        assert error.value.status_code == 404
    asyncio.run(run())
    assert len(requests) == 1


def test_native_assets_reject_changed_binary_and_remove_partial(tmp_path, monkeypatch):
    original = httpx.AsyncClient
    monkeypatch.setattr("app.native.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"changed")), **kwargs))
    assets = NativeAssets(tmp_path)
    assets.metadata = {"test": {"mame": {"source": "https://example.test/engine.zip", "size": 7, "sha256": "0" * 64}}}
    with pytest.raises(HTTPException) as error:
        asyncio.run(assets.get("test", "mame"))
    assert error.value.status_code == 502
    assert not list(tmp_path.rglob("*.part"))
    assert not list(tmp_path.rglob("*.zip"))


def test_historical_native_plan_keeps_parent_bios_and_chd(tmp_path):
    library = Library(tmp_path / "roms", tmp_path / "data", tmp_path / "media")
    folder = library.roms / "mame"
    folder.mkdir()
    chip = b"owned-program" * 256
    crc = f"{zlib.crc32(chip):08x}"
    catalog = ArcadeCatalog.parse(f'<mame><game name="game" romof="bios"><description>Game</description><rom name="chip" size="{len(chip)}" crc="{crc}"/><disk name="disk"/></game><game name="bios" isbios="yes"><description>BIOS</description></game></mame>')
    for name in ("game", "bios"):
        with zipfile.ZipFile(folder / f"{name}.zip", "w") as archive:
            archive.writestr("chip", chip)
    (folder / "game").mkdir()
    (folder / "game/disk.chd").write_bytes(b"owned-chd")
    plan = HistoricalMameCatalog(library).plan({"path": "mame/game.zip"}, catalog)
    assert plan["core"] == "mamearcade"
    assert plan["audit"] == "historical-0.130u3"
    assert {file["destination"] for file in plan["files"]} == {"game.zip", "bios.zip", "game/disk.chd"}
