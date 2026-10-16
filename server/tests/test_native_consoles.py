from fastapi.testclient import TestClient
from app.main import create_app


def test_console_library_accepts_roms_and_ignores_atari_states(tmp_path):
    app = create_app(tmp_path / "roms", tmp_path / "data", tmp_path / "media", token="")
    for system, filename in [("nes", "Example.NES"), ("atari2600", "Example.bin")]:
        folder = tmp_path / "roms" / system
        folder.mkdir()
        (folder / filename).write_bytes(b"test-cartridge")
    (tmp_path / "roms/atari2600/Example.0a.sta").write_bytes(b"saved-state")
    with TestClient(app) as client:
        games = client.get("/api/games").json()
        assert {game["system_id"] for game in games} == {"nes", "atari2600"}
        assert len(games) == 2
        for game in games:
            assert client.get(f'/api/games/{game["id"]}/download').content == b"test-cartridge"
        assert client.post("/api/systems/atari2600/upload", files={"file": ("state.sta", b"state")}).status_code == 422
        engines = client.get("/api/player/native").json()
        assert engines["systems"] == {"nes": "nestopia", "atari2600": "stella"}
        for platform in engines["platforms"].values():
            assert {"nestopia", "stella"} <= platform.keys()
