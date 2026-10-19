import io
import os
import re
import secrets
import sqlite3
import uuid
import hashlib
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import AliasChoices, BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .library import Library
from .bulk import BulkScraper
from .scraper import ScraperError
from .player import ENGINE_VERSION, INTEGRATED_SYSTEMS, PlayerAssets
from .thumbnails import LibretroThumbnails
from .artwork import ArtworkChain
from .artwork_catalogs import LaunchBoxCatalog, GameTDB
from .arcade import ArcadeCatalog, ArcadeSelector, CORES
from .mame_web import MameWebAssets, plan as mame_web_plan, VERSION as MAME_WEB_VERSION
from .native import NativeAssets, HistoricalMameCatalog, BowlingAudioCatalog, VERSION as NATIVE_VERSION
from .pinball import inspect_package, plan as pinball_plan, MAX_PACKAGE
from .pinball_runtime import PinballAssets

ROOT = Path(__file__).resolve().parents[2]


class SystemInput(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")
    name: str = Field(min_length=1, max_length=100)
    extensions: list[str] = Field(min_length=1, max_length=30)
    metadata_id: int | None = Field(default=None, gt=0, validation_alias=AliasChoices("metadata_id", "screenscraper_id"))
    emulator: str = Field(default="", max_length=100)


class GameUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    favorite: bool | None = None


class CoverChoice(BaseModel):
    provider_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    provider: Literal["auto", "libretro"] = "auto"


class BulkRequest(BaseModel):
    overwrite: bool = False
    resume: bool = False
    provider: Literal["auto", "libretro"] = "auto"


class ScrapeSettings(BaseModel):
    provider: Literal["auto", "libretro"] = "auto"


class MameAssetsRequest(BaseModel):
    files: list[str] = Field(default_factory=list, max_length=128)


def create_app(roms=None, data=None, media=None, token=None):
    library = Library(Path(roms or os.getenv("GAMECLUB_ROMS", ROOT / "roms")),
                      Path(data or os.getenv("GAMECLUB_DATA", ROOT / "data")),
                      Path(media or os.getenv("GAMECLUB_MEDIA", ROOT / "media")))
    api_token = token if token is not None else os.getenv("GAMECLUB_API_TOKEN", "")
    player_assets = PlayerAssets(library.data)
    mame_web_assets = MameWebAssets(library.data)
    arcade = ArcadeCatalog(library)
    arcade_selector = ArcadeSelector(library)
    native_arcade_selector = ArcadeSelector(library, native=True)
    native_assets = NativeAssets(library.data)
    pinball_assets = PinballAssets(library.data)
    historical_mame = HistoricalMameCatalog(library)
    bowling_audio = BowlingAudioCatalog(library)
    thumbnails = LibretroThumbnails(library.data)
    artwork = ArtworkChain(thumbnails, LaunchBoxCatalog(library.data), GameTDB(library.data))
    providers = {"auto": artwork, "libretro": artwork}

    @asynccontextmanager
    async def lifespan(app):
        await run_in_threadpool(library.scan)
        yield
        await bulk.shutdown()

    app = FastAPI(title="GameClub", version="0.9.0", lifespan=lifespan)
    app.state.library = library
    app.state.scraper = artwork
    app.state.providers = providers

    def authorize(authorization: str = Header(default="")):
        if api_token and not secrets.compare_digest(authorization, f"Bearer {api_token}"):
            raise HTTPException(401, "Token incorrecto")

    auth = [Depends(authorize)]

    def find_game(id):
        game = library.game(id)
        if not game:
            raise HTTPException(404, "Juego no encontrado")
        return game

    def image_path(id, raw):
        try:
            with Image.open(io.BytesIO(raw)) as image:
                image.thumbnail((1000, 1400))
                dest = library.media / f"{id}-{uuid.uuid4().hex}.jpg"
                image.convert("RGB").save(dest, "JPEG", quality=90)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(422, "La carátula debe ser una imagen válida") from None
        return dest

    def assign_cover(id, dest, **fields):
        old = find_game(id).get("cover")
        library.update(id, cover=dest.name, **fields)
        if old:
            (library.media / old).unlink(missing_ok=True)

    async def apply_bulk_cover(id, metadata, raw):
        dest = await run_in_threadpool(image_path, id, raw)
        fields = {"provider": metadata.get("provider", "libretro"), "title": metadata["title"]}
        if metadata.get("description"):
            fields["description"] = metadata["description"]
        await run_in_threadpool(assign_cover, id, dest, **fields)

    bulk = BulkScraper(library, artwork, apply_bulk_cover, providers=providers)
    app.state.bulk = bulk

    def mame_asset_path(relative):
        if (not relative or len(relative) > 300 or any(c in relative for c in "\\:\x00")
                or relative.startswith("/") or any(part in {"", ".", ".."} for part in relative.split("/"))
                or Path(relative).suffix.lower() not in {".zip", ".7z", ".chd"}):
            raise HTTPException(422, "Ruta de recurso MAME inválida")
        try:
            folder = library.safe_path("mame")
            path = library.safe_path(f"mame/{relative}")
            if not path.is_relative_to(folder):
                raise ValueError()
        except ValueError:
            raise HTTPException(422, "El recurso debe estar dentro de la carpeta MAME") from None
        return path

    @app.post("/api/games/{id}/mame-assets", dependencies=auth)
    def mame_assets(id: str, request: MameAssetsRequest):
        game = find_game(id)
        if game["system_id"] != "mame":
            raise HTTPException(422, "Este juego no pertenece a MAME")
        primary = game["path"].removeprefix("mame/")
        available, missing = [], []
        for relative in dict.fromkeys([primary, *request.files]):
            path = mame_asset_path(relative)
            if path.is_file():
                stat = path.stat()
                available.append({"path": relative, "size": stat.st_size, "modified": stat.st_mtime_ns,
                                  "url": "/api/mame/download?" + urlencode({"path": relative})})
            else:
                missing.append(relative)
        return {"primary": primary, "files": available, "missing": missing}

    @app.get("/api/mame/download", dependencies=auth)
    def download_mame(path: str):
        file = mame_asset_path(path)
        if not file.is_file():
            raise HTTPException(404, "Recurso MAME no disponible")
        return FileResponse(file, filename=file.name, media_type="application/octet-stream")

    @app.get("/api/games/{id}/arcade", dependencies=auth)
    async def arcade_plan(id:str):
        game=find_game(id)
        if game["system_id"]!="mame":
            raise HTTPException(422,"Este juego no pertenece a la biblioteca arcade")
        catalog=await arcade.load()
        return await run_in_threadpool(arcade.plan,game,catalog)

    @app.get("/api/games/{id}/arcade/cores", dependencies=auth)
    async def arcade_cores(id: str, identify: bool = False, web_mame: bool = False, native: bool = False):
        game = find_game(id)
        if game["system_id"] != "mame":
            raise HTTPException(422, "Este juego no pertenece a la biblioteca arcade")
        result = await (native_arcade_selector if native else arcade_selector).plans(game, identify=identify)
        if web_mame or native:
            candidate = mame_web_plan(library, game)
            if candidate:
                if native:
                    candidate = {**candidate, "core": "mamearcade", "core_name": "MAME nativo completo", "engine": "native", "engine_version": NATIVE_VERSION}
                result["candidates"].append(candidate)
        if native:
            result["candidates"] = [{**plan, "engine": "native", "engine_version": NATIVE_VERSION} for plan in result["candidates"]]
            if Path(game["path"]).stem.lower() == "wcbowl" and not any(plan["core"] == "mame2003_plus" for plan in result["candidates"]):
                try:
                    catalog = await bowling_audio.load()
                    result["candidates"].insert(0, await run_in_threadpool(bowling_audio.plan, game, catalog))
                    result["rejected"] = [plan for plan in result["rejected"] if plan["core"] != "mame2003_plus"]
                except HTTPException:
                    pass
            if not any(plan["core"] == "mamearcade" for plan in result["candidates"]):
                try:
                    catalog = await historical_mame.load()
                    result["candidates"].append(await run_in_threadpool(historical_mame.identify_plan, game, catalog))
                except HTTPException as error:
                    result["rejected"].append({"core": "mamearcade", "core_name": "MAME nativo completo", "reason": str(error.detail), "reason_code": "romset_mismatch"})
        return result

    @app.get("/api/player/native", dependencies=auth)
    def native_engines():
        return {"version": NATIVE_VERSION, "platforms": native_assets.metadata,
                "systems": {"nes": "nestopia", "atari2600": "stella"}}

    @app.get('/api/player/pinball', dependencies=auth)
    def pinball_engine_info():
        return pinball_assets.info

    @app.get('/api/player/pinball/{platform}', dependencies=auth)
    async def pinball_engine(platform: str):
        return FileResponse(await pinball_assets.get(platform, 'vpx'), media_type='application/zip')

    @app.get('/api/games/{id}/pinball', dependencies=auth)
    def pinball_manifest(id: str):
        game = find_game(id)
        if game['system_id'] != 'vpinball':
            raise HTTPException(422, 'Este juego no es una mesa Visual Pinball')
        return pinball_plan(library, game)

    @app.get("/api/player/native/{platform}/{core}", dependencies=auth)
    async def native_engine_asset(platform: str, core: str):
        return FileResponse(await native_assets.get(platform, core), media_type="application/zip",
                            headers={"Cache-Control": "public, max-age=31536000, immutable"})

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.9.0"}

    @app.get("/api/player", dependencies=auth)
    def player_info():
        return {"engine": "EmulatorJS", "version": ENGINE_VERSION, "systems": INTEGRATED_SYSTEMS,
                "arcade_cores": [{"id": key, "name": value["name"]} for key, value in CORES.items()] +
                    [{"id": "mame_web", "name": "MAME 0.232 por controlador", "version": MAME_WEB_VERSION}]}

    @app.get("/api/player/assets/{relative:path}", dependencies=auth)
    async def engine_asset(relative: str):
        path = await player_assets.get(relative)
        return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})

    @app.get("/api/player/mame-web/{driver}/{name}", dependencies=auth)
    async def mame_web_asset(driver: str, name: str):
        path = await mame_web_assets.get(driver, name)
        return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})

    @app.get("/api/settings", dependencies=auth)
    def settings():
        return {"scrape_job": bulk.public(), "scrape_provider": "auto", "scrape_order": ["libretro", "launchbox", "gametdb"],
                "providers": [{"name": "Libretro Thumbnails", "implemented": True, "requires_key": False,
                               "requires_account": False, "url": "https://thumbnails.libretro.com"},
                              {"name": "LaunchBox", "implemented": True, "requires_key": False, "requires_account": False,
                               "url": "https://gamesdb.launchbox-app.com"},
                              {"name": "GameTDB", "implemented": True, "requires_key": False, "requires_account": False,
                               "url": "https://www.gametdb.com"},
                              {"name": "Subida manual", "implemented": True, "requires_key": False, "requires_account": False}],
                "roms_path": str(library.roms)}

    @app.put("/api/settings/scrape", dependencies=auth)
    def save_scrape_settings(request: ScrapeSettings):
        library.save_setting("scrape_provider", request.provider)
        return settings()

    @app.get("/api/scrape/job", dependencies=auth)
    def scrape_status():
        return bulk.public()

    @app.post("/api/scrape/job", status_code=202, dependencies=auth)
    async def start_scrape(request: BulkRequest):
        try:
            return await bulk.start(request.overwrite, request.resume, request.provider)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        except ScraperError as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/api/scrape/job/cancel", dependencies=auth)
    async def cancel_scrape():
        return await bulk.cancel()

    @app.get("/api/systems", dependencies=auth)
    def systems(include_empty: bool = False):
        return [s for s in library.systems() if include_empty or s["game_count"]]

    @app.post("/api/systems", status_code=201, dependencies=auth)
    def add_system(config: SystemInput):
        if any(not re.fullmatch(r"\.[a-z0-9]{1,10}", ext) for ext in config.extensions):
            raise HTTPException(422, "Extensiones inválidas; ejemplo: .gba")
        try:
            library.add_system(config.model_dump())
        except sqlite3.IntegrityError:
            raise HTTPException(409, "La consola ya existe") from None
        return library.get_system(config.id)

    @app.post("/api/scan", dependencies=auth)
    def scan():
        return {"game_count": library.scan()}

    @app.get("/api/games", dependencies=auth)
    def games(system_id: str | None = None, q: str = "", favorites: bool = False,
              category: Literal['pinball'] | None = None):
        return [game for game in library.games(system_id, q, favorites) if category is None or game.get('category') == category]

    @app.patch("/api/games/{id}", dependencies=auth)
    def update(id: str, changes: GameUpdate):
        find_game(id)
        fields = changes.model_dump(exclude_none=True)
        if fields:
            library.update(id, **fields)
        return Library.public(find_game(id))

    @app.post("/api/systems/{system_id}/upload", status_code=201, dependencies=auth)
    def upload(system_id: str, file: UploadFile):
        system = library.get_system(system_id)
        if not system:
            raise HTTPException(404, "Consola no encontrada")
        name = file.filename or ""
        if (not name or name in {".", ".."} or any(c in name for c in '/\\<>:"|?*')
                or any(ord(c) < 32 for c in name) or len(name) > 200):
            raise HTTPException(422, "Nombre de archivo inválido")
        if Path(name).suffix.lower() not in system["extensions"]:
            raise HTTPException(422, "Formato no admitido para esta consola")
        folder = library.safe_path(system_id)
        folder.mkdir(exist_ok=True)
        dest = library.safe_path(f"{system_id}/{name}")
        temp = folder / f".{uuid.uuid4().hex}.upload"
        try:
            with temp.open("xb") as output:
                while chunk := file.file.read(1024 * 1024):
                    output.write(chunk)
                    if system_id == 'vpinball' and output.tell() > MAX_PACKAGE:
                        raise HTTPException(413, 'Máximo 4 GiB por paquete de pinball')
            if temp.stat().st_size == 0:
                raise HTTPException(422, "El archivo está vacío")
            if system_id == 'vpinball':
                inspect_package(temp, name)
            # Serializar publicación y escaneos evita sobrescribir juegos existentes.
            with library.lock:
                if dest.exists():
                    raise HTTPException(409, "Ya existe un archivo con ese nombre")
                temp.rename(dest)
                library.scan()
        finally:
            temp.unlink(missing_ok=True)
            file.file.close()
        return {"filename": name, "system_id": system_id}

    @app.get("/api/games/{id}/download", dependencies=auth)
    def download(id: str):
        game = find_game(id)
        try:
            path = library.safe_path(game["path"])
        except ValueError:
            raise HTTPException(404, "Archivo no disponible") from None
        if not path.is_file():
            raise HTTPException(404, "Archivo no disponible; vuelve a escanear")
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")

    @app.get("/api/games/{id}/cover", dependencies=auth)
    def cover(id: str):
        name = find_game(id)["cover"]
        if not name or not (library.media / name).is_file():
            raise HTTPException(404, "Sin carátula")
        return FileResponse(library.media / name, media_type="image/jpeg")

    def screenshot_status(id):
        game=find_game(id)
        check=library.setting(f"screenshots:{id}") or {}
        checked=check.get("title")==game["title"] and time.time()-check.get("time",0)<7*86400
        return {"images":library.screenshots(id),"checked":checked}

    @app.get("/api/games/{id}/screenshots",dependencies=auth)
    def screenshots(id:str):
        return screenshot_status(id)

    @app.get("/api/games/{id}/screenshots/{image_id}",dependencies=auth)
    def screenshot_image(id:str,image_id:str):
        find_game(id)
        name=library.screenshot_file(id,image_id)
        if not name or not (library.media/name).is_file():
            raise HTTPException(404,"Captura no encontrada")
        return FileResponse(library.media/name,media_type="image/jpeg")

    @app.post("/api/games/{id}/screenshots/refresh",dependencies=auth)
    async def refresh_screenshots(id:str):
        game=find_game(id)
        system=library.get_system(game["system_id"])
        if not system.get("metadata_id"):
            library.save_setting(f"screenshots:{id}",{"title":game["title"],"time":time.time()})
            return screenshot_status(id)
        try:
            images=await thumbnails.screenshots(game["title"],system["metadata_id"])
        except ScraperError as error:
            raise HTTPException(502,str(error)) from None
        for image in images:
            image_id=hashlib.sha256((id+image["source_id"]).encode()).hexdigest()[:24]
            if library.screenshot_file(id,image_id):
                continue
            path=await run_in_threadpool(image_path,"screenshot-"+image_id,image["data"])
            await run_in_threadpool(library.add_screenshot,image_id,id,path.name,image["label"],"libretro")
        await run_in_threadpool(library.save_setting,f"screenshots:{id}",{"title":game["title"],"time":time.time()})
        return screenshot_status(id)

    @app.post("/api/games/{id}/screenshots",dependencies=auth)
    async def upload_screenshot(id:str,file:UploadFile):
        find_game(id)
        try:
            raw=await file.read(10*1024*1024+1)
        finally:
            await file.close()
        if len(raw)>10*1024*1024:
            raise HTTPException(413,"Máximo 10 MB por captura")
        image_id=uuid.uuid4().hex
        path=await run_in_threadpool(image_path,"screenshot-"+image_id,raw)
        await run_in_threadpool(library.add_screenshot,image_id,id,path.name,file.filename or "Captura propia","manual")
        return screenshot_status(id)

    @app.post("/api/games/{id}/cover", dependencies=auth)
    async def upload_cover(id: str, file: UploadFile):
        find_game(id)
        try:
            raw = await file.read(10 * 1024 * 1024 + 1)
        finally:
            await file.close()
        if len(raw) > 10 * 1024 * 1024:
            raise HTTPException(413, "Máximo 10 MB por carátula")
        dest = await run_in_threadpool(image_path, id, raw)
        await run_in_threadpool(assign_cover, id, dest, provider="manual")
        return {"cover_url": f"/api/games/{id}/cover"}

    @app.get("/api/games/{id}/scrape", dependencies=auth)
    async def candidates(id: str, provider: Literal["auto", "libretro"] = "auto", q: str = ""):
        game = find_game(id)
        system = library.get_system(game["system_id"])
        if not system.get("metadata_id"):
            raise HTTPException(422, "No hay catálogo público configurado para esta consola")
        try:
            return await providers[provider].search(q[:200] or game["title"], system["metadata_id"])
        except ScraperError as error:
            raise HTTPException(502, str(error)) from None

    @app.post("/api/games/{id}/scrape", dependencies=auth)
    async def apply_candidate(id: str, choice: CoverChoice):
        game = find_game(id)
        system = library.get_system(game["system_id"])
        if not system.get("metadata_id"):
            raise HTTPException(422, "No hay catálogo público configurado para esta consola")
        try:
            metadata, raw = await providers[choice.provider].cover(choice.provider_id, system["metadata_id"])
            await apply_bulk_cover(id, metadata, raw)
        except ScraperError as error:
            raise HTTPException(502, str(error)) from None
        return Library.public(find_game(id))

    return app


app = create_app()
