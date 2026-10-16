import asyncio
import re
import uuid
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import HTTPException


ENGINE_VERSION = "4.2.3"
INTEGRATED_SYSTEMS = {
    "gb": "gambatte", "gbc": "gambatte", "gba": "mgba",
    "snes": "snes9x", "nds": "desmume", "n64": "mupen64plus_next",
    "mame": "mame2003_plus",
}


class PlayerAssets:
    """Motores fijados a una versión y cacheados en el volumen persistente."""
    def __init__(self, data: Path):
        self.root = data / "player" / f"emulatorjs-{ENGINE_VERSION}"
        self.root.mkdir(parents=True, exist_ok=True)
        self.locks = {}

    def path(self, relative):
        if (not re.fullmatch(r"[a-zA-Z0-9_./-]{1,240}", relative)
                or any(part in {"", ".", ".."} or part.startswith(".") for part in relative.split("/"))):
            raise HTTPException(422, "Ruta del motor inválida")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise HTTPException(422, "Ruta del motor inválida")
        return path

    async def get(self, relative):
        path = self.path(relative)
        async with self.locks.setdefault(relative, asyncio.Lock()):
            if path.is_file():
                return path
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.part")
            url = f"https://cdn.emulatorjs.org/{ENGINE_VERSION}/data/{quote(relative, safe='/')}"
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    async with client.stream("GET", url) as response:
                        if response.status_code == 404:
                            raise HTTPException(404, "Este recurso del motor no está disponible")
                        response.raise_for_status()
                        size = 0
                        with temporary.open("xb") as output:
                            async for chunk in response.aiter_bytes():
                                size += len(chunk)
                                if size > 160 * 1024 * 1024:
                                    raise HTTPException(502, "El recurso del motor supera el tamaño permitido")
                                output.write(chunk)
                        if size == 0:
                            raise HTTPException(502, "El proveedor devolvió un motor vacío")
                temporary.replace(path)
            except httpx.HTTPError:
                raise HTTPException(502, "No se pudo preparar el motor integrado. Comprueba la conexión a Internet de la Raspberry.") from None
            finally:
                temporary.unlink(missing_ok=True)
            return path
