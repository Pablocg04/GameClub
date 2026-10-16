import asyncio
import gzip
import hashlib
import uuid
from pathlib import Path

import httpx
from fastapi import HTTPException

VERSION = "mame-0.232-emularity-pinned-v1"
DRIVERS = {
    "nbmj8688": {"js": "04276fe25bf6727711e59b9c2caf36a2418d004d", "wasm": "5d4b1e9c4231e86080b69e86a577dc358ad6fa9d"},
    "highvdeo": {"js": "f39dbf8956d437d44bf745dce4e33cc8f2a6f0d2", "wasm": "859dc858107117647b7b99ddc4952c2ec6dc49ab"},
    "caswin": {"js": "9c702260666c891394965576f7c028c94b87074b", "wasm": "3e50251b63c8a0fe1b5cc2860112a86933dd4809"},
}
GAMES = {
    "barline": ("nbmj8688", "Barline (Japan?)"),
    "cfever61": ("highvdeo", "Casino Fever 6.1"),
    "rcasino": ("caswin", "Royal Casino"),
}


def plan(library, game):
    path = library.safe_path(game["path"])
    code = path.stem
    if code not in GAMES or path.suffix.lower() != ".zip":
        return None
    driver, title = GAMES[code]
    stat = path.stat()
    files = [{"path": game["path"].removeprefix("mame/"), "destination": path.name,
              "size": stat.st_size, "modified": stat.st_mtime_ns}]
    signature = hashlib.sha256(f"{driver}/{stat.st_size}/{stat.st_mtime_ns}/{DRIVERS[driver]}".encode()).hexdigest()[:24]
    return {"core": "mame_web", "core_name": f"MAME 0.232 · {driver}", "engine": "mame_web",
            "engine_version": VERSION, "driver": driver, "game_code": code, "title": title,
            "files": files, "signature": signature, "audit": "runtime",
            "note": "MAME valida el romset al arrancar; motor independiente de EmulatorJS"}


class MameWebAssets:
    def __init__(self, data: Path):
        self.root = data / "player" / "mame-web-v1"
        self.root.mkdir(parents=True, exist_ok=True)
        self.locks = {}

    async def get(self, driver, name):
        if driver not in DRIVERS or name not in {f"mame{driver}.js", f"mame{driver}.wasm"}:
            raise HTTPException(422, "Recurso MAME web no permitido")
        path = self.root / name
        async with self.locks.setdefault(name, asyncio.Lock()):
            if path.is_file():
                return path
            temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.part")
            try:
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    response = await client.get(f"https://archive.org/download/emularity_engine_v1/{name}.gz")
                    response.raise_for_status()
                    if len(response.content) > 32 * 1024 * 1024:
                        raise HTTPException(502, "Motor MAME web demasiado grande")
                    expected = DRIVERS[driver][name.rsplit(".", 1)[1]]
                    if hashlib.sha1(response.content).hexdigest() != expected:
                        raise HTTPException(502, "El motor MAME web no coincide con la versión verificada")
                    data = gzip.decompress(response.content)
                    if len(data) > 160 * 1024 * 1024:
                        raise HTTPException(502, "Motor MAME web descomprimido demasiado grande")
                    temporary.write_bytes(data)
                    temporary.replace(path)
            except (httpx.HTTPError, gzip.BadGzipFile, EOFError):
                raise HTTPException(502, "No se pudo preparar el motor MAME web. Comprueba Internet en la Raspberry.") from None
            finally:
                temporary.unlink(missing_ok=True)
            return path
