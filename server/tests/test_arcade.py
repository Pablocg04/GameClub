import asyncio
import zipfile
import zlib
import pytest
from fastapi import HTTPException
from app.arcade import ArcadeCatalog
from app.arcade import ArcadeSelector
from app.library import Library


def test_arcade_audit_accepts_matching_chips_and_downloads_parent(tmp_path):
    library=Library(tmp_path/"roms",tmp_path/"data",tmp_path/"media")
    (library.roms/"mame").mkdir()
    chip=b"owned-test-chip"
    crc=f"{zlib.crc32(chip):08x}"
    xml=f'<mame><game name="clone" romof="parent"><description>Clone</description><rom name="chip.bin" size="{len(chip)}" crc="{crc}"/></game><game name="parent"><description>Parent</description></game></mame>'
    catalog=ArcadeCatalog.parse(xml)
    for name in ("clone","parent"):
        with zipfile.ZipFile(library.roms/"mame"/f"{name}.zip","w") as archive:
            archive.writestr("chip.bin" if name=="parent" else "other.bin",chip if name=="parent" else b"other")
    arcade=ArcadeCatalog(library)
    game={"path":"mame/clone.zip"}
    plan=arcade.plan(game,catalog)
    assert plan["core"]=="mame2003_plus"
    assert {item["destination"] for item in plan["files"]}=={"clone.zip","parent.zip"}
    (library.roms/"mame"/"parent.zip").unlink()
    with pytest.raises(HTTPException,match="romset") as error:
        arcade.plan(game,catalog)
    assert error.value.status_code==422
    with pytest.raises(HTTPException):
        arcade.plan({"path":"mame/unknown.zip"},catalog)


def test_selector_keeps_other_cores_when_one_catalog_is_unavailable(tmp_path, monkeypatch):
    library=Library(tmp_path/"roms",tmp_path/"data",tmp_path/"media")
    selector=ArcadeSelector(library)
    async def load(self):
        if self.core=="mame2003_plus":
            raise HTTPException(502,"Catálogo no disponible")
        return {}
    monkeypatch.setattr(ArcadeCatalog,"load",load)
    monkeypatch.setattr(ArcadeCatalog,"plan",lambda self,game,catalog:{"core":self.core})
    result=asyncio.run(selector.plans({"path":"mame/test.zip"}))
    assert [item["core"] for item in result["candidates"]]==["mame2003","fbneo"]
    assert result["rejected"][0]["retryable"] is True


def test_fbneo_lets_core_check_alternative_bios_but_rejects_missing_game_chips(tmp_path):
    library=Library(tmp_path/"roms",tmp_path/"data",tmp_path/"media")
    (library.roms/"mame").mkdir()
    chip=b"game"*256
    crc=f"{zlib.crc32(chip):08x}"
    data=f'<datafile><game name="game" romof="bios"><rom name="game.bin" size="{len(chip)}" crc="{crc}"/><rom name="firmware.bin" size="131072" crc="12345678"/></game><game name="bios" isbios="yes"><rom name="firmware.bin" size="131072" crc="12345678"/></game></datafile>'
    catalog=ArcadeCatalog.parse(data)
    with zipfile.ZipFile(library.roms/"mame/game.zip","w") as archive:
        archive.writestr("game.bin",chip)
    arcade=ArcadeCatalog(library,"fbneo")
    assert arcade.plan({"path":"mame/game.zip"},catalog)["audit"]=="partial"
    with zipfile.ZipFile(library.roms/"mame/game.zip","w") as archive:
        archive.writestr("wrong.bin",b"wrong")
    with pytest.raises(HTTPException) as error:
        arcade.plan({"path":"mame/game.zip"},catalog)
    assert "game.bin" in error.value.detail


def test_historical_filename_is_resolved_by_chips_without_changing_original(tmp_path):
    library = Library(tmp_path / "roms", tmp_path / "data", tmp_path / "media")
    (library.roms / "mame").mkdir()
    chip = b"version-H-program" * 1024
    crc = f"{zlib.crc32(chip):08x}"
    catalog = ArcadeCatalog.parse(f'<datafile><game name="sbasketb"><description>Version I</description>'
        '<rom name="program-I" size="8192" crc="12345678"/></game>'
        f'<game name="sbasketh" cloneof="sbasketb"><description>Version H</description>'
        f'<rom name="program-H" size="{len(chip)}" crc="{crc}"/></game></datafile>')
    source = library.roms / "mame/sbasketb.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("program-H", chip)
    original = source.read_bytes()
    provider = ArcadeCatalog(library, "fbneo")
    with pytest.raises(HTTPException):
        provider.plan({"path": "mame/sbasketb.zip"}, catalog)
    plan = provider.identify_plan({"path": "mame/sbasketb.zip"}, catalog)
    assert plan["game_code"] == "sbasketh"
    assert plan["source_code"] == "sbasketb"
    assert plan["identified_by"] == "content"
    assert [(item["path"], item["destination"]) for item in plan["files"]] == [("sbasketb.zip", "sbasketh.zip")]
    assert source.read_bytes() == original


def test_shared_graphics_do_not_identify_a_different_game_revision(tmp_path):
    library = Library(tmp_path / "roms", tmp_path / "data", tmp_path / "media")
    (library.roms / "mame").mkdir()
    graphics = b"common-graphics" * 4096
    crc = f"{zlib.crc32(graphics):08x}"
    catalog = ArcadeCatalog.parse(f'<datafile><game name="other"><rom name="graphics" size="{len(graphics)}" crc="{crc}"/>'
                                 '<rom name="required-program" size="32768" crc="12345678"/></game></datafile>')
    with zipfile.ZipFile(library.roms / "mame/unknown.zip", "w") as archive:
        archive.writestr("graphics", graphics)
    with pytest.raises(HTTPException) as error:
        ArcadeCatalog(library, "fbneo").identify_plan({"path": "mame/unknown.zip"}, catalog)
    assert "no está incluido" in error.value.detail


def test_shared_firmware_subset_does_not_identify_an_unknown_game(tmp_path):
    library = Library(tmp_path / "roms", tmp_path / "data", tmp_path / "media")
    (library.roms / "mame").mkdir()
    firmware = b"shared-firmware" * 1024
    crc = f"{zlib.crc32(firmware):08x}"
    catalog = ArcadeCatalog.parse(f'<mame><game name="firmware-device"><rom name="firmware" size="{len(firmware)}" crc="{crc}"/></game></mame>')
    with zipfile.ZipFile(library.roms / "mame/unknown.zip", "w") as archive:
        archive.writestr("firmware", firmware)
        archive.writestr("game-program", b"unknown-game-program" * 65536)
    with pytest.raises(HTTPException):
        ArcadeCatalog(library).identify_plan({"path": "mame/unknown.zip"}, catalog)
