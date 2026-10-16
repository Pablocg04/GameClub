import asyncio
import gzip
import hashlib
import json
from pathlib import Path

import httpx
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from .arcade import ArcadeCatalog

ROOT = Path(__file__).parent
VERSION = "native-1"


class NativeAssets:
    def __init__(self, data):
        self.directory = data / "native-cores" / "v1"
        self.metadata = json.loads((ROOT / "native_cores.json").read_text(encoding="utf-8"))
        self.locks = {}
        self.verified = set()

    async def get(self, platform, core):
        entry = self.metadata.get(platform, {}).get(core)
        if entry is None:
            raise HTTPException(404, "Motor nativo no disponible para esta plataforma")
        key = (platform, core)
        async with self.locks.setdefault(key, asyncio.Lock()):
            destination = self.directory / platform / f"{core}.zip"
            if key in self.verified and destination.is_file():
                return destination

            def valid():
                if not destination.is_file() or destination.stat().st_size != entry["size"]:
                    return False
                with destination.open("rb") as file:
                    return hashlib.file_digest(file, "sha256").hexdigest() == entry["sha256"]

            if not await run_in_threadpool(valid):
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(".part")
                digest, size = hashlib.sha256(), 0
                try:
                    async with httpx.AsyncClient(timeout=240, follow_redirects=True) as client:
                        async with client.stream("GET", entry["source"]) as response:
                            response.raise_for_status()
                            with temporary.open("wb") as output:
                                async for chunk in response.aiter_bytes(1024 * 1024):
                                    size += len(chunk)
                                    if size > entry["size"]:
                                        raise ValueError("Tamaño de motor distinto del fijado")
                                    digest.update(chunk)
                                    output.write(chunk)
                    if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                        raise ValueError("La huella del motor no coincide con la versión fijada")
                    temporary.replace(destination)
                except (httpx.HTTPError, ValueError):
                    raise HTTPException(502, "No se pudo recuperar el motor nativo fijado; restaura su caché original") from None
                finally:
                    temporary.unlink(missing_ok=True)
            self.verified.add(key)
            return destination


class HistoricalMameCatalog(ArcadeCatalog):
    """Dependencias del pack 0.130u3; la validación final corresponde al motor actual."""
    def __init__(self, library):
        self.library, self.core, self.name = library, "mamearcade", "MAME nativo completo"
        self.games = None

    async def load(self):
        if self.games is None:
            def read():
                return json.loads(gzip.decompress((ROOT / "native_mame0130.json.gz").read_bytes()))
            self.games = await run_in_threadpool(read)
        return self.games

    def plan(self, game, catalog, code=None):
        result = super().plan(game, catalog, code)
        return {**result, "engine": "native", "engine_version": VERSION,
                "audit": "historical-0.130u3", "note": "Dependencias del ROMset histórico; MAME nativo valida su compatibilidad final al arrancar."}


class BowlingAudioCatalog(HistoricalMameCatalog):
    """Perfil verificado con el juego completo v1.66 y su revisión de audio histórica.

    Se auditan TODOS los CRC/tamaños contra el perfil conocido, no se desactiva
    la auditoría general ni se cambian los ZIP. El motor admite las advertencias
    de revisión de audio al cargar estos archivos.
    """
    def __init__(self, library):
        self.library, self.core, self.name = library, "mame2003_plus", "MAME 2003-Plus · Bowling v1.66"
        self.games = None

    async def load(self):
        if self.games is None:
            self.games = json.loads((ROOT / "native_bowling.json").read_text(encoding="utf-8"))["games"]
        return self.games

    def plan(self, game, catalog, code=None):
        result = super().plan(game, catalog, code)
        return {**result, "audit": "verified-historical-audio", "compatibility_profile": "wcbowl-166-audio",
                "note": "World Class Bowling v1.66 completo, con revisión histórica de audio; vídeo, entradas y salida de audio comprobados con este perfil."}
