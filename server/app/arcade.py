import asyncio
import json
import hashlib
import re
import zipfile
import xml.etree.ElementTree as ET

import httpx
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from pathlib import PurePosixPath


CORE = "mame2003_plus"
CATALOG_URL = "https://raw.githubusercontent.com/libretro/mame2003-plus-libretro/c1de17eb547a618b99754a3d708a07dd77a42021/metadata/mame2003-plus.xml"
CORES = {
    "mame2003_plus": {"name": "MAME 2003-Plus", "url": CATALOG_URL, "revision": "2025"},
    "mame2003": {"name": "MAME 2003 · 0.78", "url": "https://raw.githubusercontent.com/libretro/mame2003-libretro/ef6a38e7b56efb67607ab5875ea02a09517b4a19/metadata/mame2003.xml", "revision": "2023"},
    "fbneo": {"name": "FinalBurn Neo", "url": "https://raw.githubusercontent.com/libretro/FBNeo/e8291a39f637d23900d6998ea7f67648856201f9/dats/FinalBurn%20Neo%20(ClrMame%20Pro%20XML%2C%20Arcade%20only).dat", "revision": "2025-06-12"},
}
NATIVE_CORES = CORES


class ArcadeCatalog:
    def __init__(self, library, core=CORE):
        self.library = library
        self.core = core
        self.config = NATIVE_CORES[core]
        self.name = self.config["name"]
        self.cache = library.data / "arcade" / f"{core}-{self.config['revision']}-v2.json"
        self.games = None
        self.lock = asyncio.Lock()

    @staticmethod
    def parse(data):
        root = ET.fromstring(data)
        games = {}
        for game in root:
            if game.tag not in {"game", "machine"} or not game.get("name"):
                continue
            bios = next((item.get("name") for item in game.findall("biosset") if item.get("default") == "yes"), None)
            games[game.get("name")] = {
                "title": game.findtext("description") or game.get("name"),
                "bios": game.get("isbios") == "yes",
                "parents": list(set(filter(None, [game.get("romof"), game.get("cloneof")]))),
                "roms": [{"name": item.get("name"), "crc": item.get("crc"), "size": int(item.get("size") or 0)}
                         for item in game.findall("rom") if item.get("status") != "nodump"
                         and (not bios or not item.get("bios") or item.get("bios") == bios)],
                "disks": [item.get("name") for item in game.findall("disk") if item.get("name")],
            }
        return games

    async def load(self):
        async with self.lock:
            if self.games is not None:
                return self.games
            if self.cache.exists():
                self.games = json.loads(self.cache.read_text(encoding="utf-8"))
                return self.games
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    response = await client.get(self.config["url"])
                    response.raise_for_status()
                    if len(response.content) > self.config.get("max_catalog_size", 40 * 1024 * 1024):
                        raise ValueError()
                    self.games = await run_in_threadpool(self.parse, response.content)
            except (httpx.HTTPError, ET.ParseError, ValueError):
                raise HTTPException(502, "No se pudo preparar el catálogo del núcleo arcade") from None
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            self.cache.write_text(json.dumps(self.games), encoding="utf-8")
            return self.games

    def plan(self, game, catalog, code=None):
        primary = game["path"].removeprefix("mame/")
        source_code = PurePosixPath(primary).stem
        code = code or source_code
        if (not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", code)
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", source_code)
                or not primary.lower().endswith(".zip")):
            raise HTTPException(422, "El núcleo arcade integrado necesita el ZIP del romset")
        if code not in catalog:
            raise HTTPException(422, f"El juego {code} no está incluido en {self.name}")
        if catalog[code]["bios"]:
            raise HTTPException(422, "Este archivo es una BIOS, no un juego ejecutable")
        sets, queue = {}, [code]
        while queue:
            current = queue.pop()
            if current in sets:
                continue
            if current not in catalog or len(sets) >= 64:
                raise HTTPException(422, "No se pudieron resolver las dependencias arcade")
            sets[current] = catalog[current]
            queue.extend(catalog[current]["parents"])
        files, inventories, seen = [], [], set()
        for name, info in sets.items():
            relative = primary if name == code else f"{name}.zip"
            path = self.library.safe_path(f"mame/{relative}")
            if path.is_file() and path not in seen:
                try:
                    with zipfile.ZipFile(path) as archive:
                        inventory = {(member.CRC, member.file_size) for member in archive.infolist() if not member.is_dir()}
                except (zipfile.BadZipFile, OSError):
                    raise HTTPException(422, f"El archivo {relative} no es un ZIP válido") from None
                inventories.append(inventory)
                seen.add(path)
                stat = path.stat()
                files.append({"path": relative, "destination": f"{name}.zip", "size": stat.st_size, "modified": stat.st_mtime_ns})
            for disk in info["disks"]:
                relative = f"{name}/{disk}.chd"
                path = self.library.safe_path(f"mame/{relative}")
                if path.is_file():
                    stat = path.stat()
                    files.append({"path": relative, "destination": relative, "size": stat.st_size, "modified": stat.st_mtime_ns})
        inventory = set().union(*inventories) if inventories else set()
        bios_chips = {rom["crc"] for info in sets.values() if info["bios"] for rom in info["roms"]}
        # Auditoría de chips por CRC y tamaño; el núcleo realiza su validación final.
        missing = [rom["name"] for rom in catalog[code]["roms"]
                   if rom["crc"] and (int(rom["crc"], 16), rom["size"]) not in inventory
                   and not (self.core == "fbneo" and (rom["crc"] in bios_chips or rom["size"] < 512))]
        for name, info in sets.items():
            if info["bios"] and self.core != "fbneo":
                missing.extend(rom["name"] for rom in info["roms"] if rom["crc"]
                               and (int(rom["crc"], 16), rom["size"]) not in inventory)
        if missing:
            names = ", ".join(dict.fromkeys(missing))
            raise HTTPException(422, f"Este romset no coincide con {self.name}. Faltan chips compatibles: {names[:1600]}")
        signature = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:24]
        return {"core": self.core, "core_name": self.name, "title": catalog[code]["title"], "game_code": code,
                "source_code": source_code, "identified_by": "content" if source_code != code else "filename",
                "files": files, "signature": signature, "engine_version": "4.2.3",
                "audit": "partial" if self.core == "fbneo" else "chips",
                "note": "El núcleo valida las BIOS alternativas y los componentes opcionales al arrancar" if self.core == "fbneo" else ""}

    def identify_plan(self, game, catalog):
        """Un código MAME puede cambiar de revisión entre romsets históricos.

        El nombre del ZIP no basta: se prueban candidatos por CRC/tamaño y
        solo se acepta uno que supere la auditoría completa de sus chips.
        """
        try:
            return self.plan(game, catalog)
        except HTTPException as original:
            if original.status_code != 422:
                raise
            path = self.library.safe_path(game["path"])
            try:
                with zipfile.ZipFile(path) as archive:
                    present = {(member.CRC, member.file_size) for member in archive.infolist()
                               if not member.is_dir() and member.file_size >= 512}
            except (zipfile.BadZipFile, OSError):
                raise original from None
            bios = {rom["crc"] for item in catalog.values() if item["bios"] for rom in item["roms"]}
            primary_size = sum(size for _, size in present)
            ranked = []
            for code, item in catalog.items():
                if item["bios"]:
                    continue
                chips = {(int(rom["crc"], 16), rom["size"]) for rom in item["roms"]
                         if rom["crc"] and rom["size"] >= 512 and rom["crc"] not in bios}
                matched = chips & present
                if matched:
                    matched_size = sum(size for _, size in matched)
                    # Una BIOS/MCU compartida no identifica el juego completo.
                    if not primary_size or matched_size / primary_size < .8:
                        continue
                    total_size = sum(size for _, size in chips)
                    ranked.append((matched_size / total_size, len(matched), code))
            ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
            for _, _, code in ranked[:32]:
                try:
                    return self.plan(game, catalog, code=code)
                except HTTPException as error:
                    if error.status_code != 422:
                        raise
            raise original from None


class ArcadeSelector:
    def __init__(self, library, native=False):
        self.library = library
        self.catalogs = {core: ArcadeCatalog(library, core) for core in (NATIVE_CORES if native else CORES)}

    async def plans(self, game, identify=False):
        candidates, rejected = [], []
        for core, provider in self.catalogs.items():
            catalog = None
            try:
                catalog = await provider.load()
                resolve = provider.identify_plan if identify else provider.plan
                plan = await run_in_threadpool(resolve, game, catalog)
                candidates.append(plan)
            except HTTPException as error:
                source_code = PurePosixPath(game["path"]).stem
                reason_code = ("catalog_unavailable" if error.status_code >= 500 else
                               "unsupported_game" if catalog is not None and source_code not in catalog else "romset_mismatch")
                rejected.append({"core": core, "core_name": provider.name,
                                 "reason": error.detail, "reason_code": reason_code, "retryable": error.status_code >= 500})
        return {"candidates": candidates, "rejected": rejected}
