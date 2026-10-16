import asyncio
import copy
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

from starlette.concurrency import run_in_threadpool

from .scraper import ScraperError


def normalized(title):
    text = unicodedata.normalize("NFKD", title.casefold())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


def best_candidate(title, candidates):
    """Evitar asignar automáticamente secuelas o resultados ambiguos."""
    candidates = list({c["id"]: c for c in candidates}.values())
    target = normalized(title)
    exact = [c for c in candidates if normalized(c["title"]) == target]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    def numbers(text):
        return re.findall(r"\b(?:\d+|i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi)\b", text)

    scored = sorted([(SequenceMatcher(None, target, normalized(c["title"])).ratio(), c)
                     for c in candidates
                     if numbers(target) == numbers(normalized(c["title"]))],
                    key=lambda pair: pair[0], reverse=True)
    if scored and scored[0][0] >= .93 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= .05):
        return scored[0][1]
    return None


class BulkScraper:
    def __init__(self, library, scraper, apply, providers=None):
        self.library, self.scraper, self.apply = library, scraper, apply
        self.providers = providers or {"auto": scraper, "libretro": scraper}
        self.task = None
        self.control_lock = asyncio.Lock()
        self.state = library.setting("bulk_scrape") or {"status": "idle", "total": 0, "processed": 0,
            "updated": 0, "skipped": 0, "failed": 0, "recent": [], "_pending": []}
        if self.state["status"] in {"running", "cancelling"}:
            self.state.update(status="interrupted", current_title="", message="El servidor se reinició. Puedes continuar el scrape.")
            library.save_setting("bulk_scrape", self.state)
        if self.state.get("provider") != "auto":
            self.state["provider"] = "auto"
            library.save_setting("bulk_scrape", self.state)

    @property
    def active(self):
        return self.state["status"] in {"running", "cancelling"}

    def public(self):
        result = copy.deepcopy({key: value for key, value in self.state.items() if not key.startswith("_")})
        result["can_resume"] = bool(self.state.get("_pending")) and not self.active
        return result

    async def persist(self):
        await run_in_threadpool(self.library.save_setting, "bulk_scrape", copy.deepcopy(self.state))

    async def start(self, overwrite=False, resume=False, provider="auto"):
        async with self.control_lock:
            return await self._start(overwrite, resume, provider)

    async def _start(self, overwrite, resume, provider):
        if self.active or (self.task and not self.task.done()):
            raise ValueError("Ya hay un scrape en ejecución")
        provider = self.state.get("provider", "auto") if resume else provider
        if provider not in self.providers:
            raise ValueError("Proveedor desconocido")
        self.providers[provider].require_configuration()
        if resume:
            if not self.public()["can_resume"]:
                raise ValueError("No hay un scrape pendiente para continuar")
            self.state.update(status="running", message="", current_title="")
        else:
            games = await run_in_threadpool(self.library.games)
            pending = [g["id"] for g in games if overwrite or not g["cover_url"]]
            self.state = {"id": uuid.uuid4().hex, "status": "running", "total": len(pending),
                "processed": 0, "updated": 0, "skipped": 0, "failed": 0,
                "already_covered": len(games) - len(pending), "overwrite": overwrite,
                "provider": provider,
                "current_title": "", "message": "", "recent": [], "_pending": pending,
                "started_at": datetime.now(timezone.utc).isoformat()}
        await self.persist()
        self.task = asyncio.create_task(self.run())
        return self.public()

    async def cancel(self):
        if self.active:
            self.state.update(status="cancelling", message="Se cancelará al terminar el juego actual.")
            await self.persist()
        return self.public()

    def record(self, title, status, message):
        self.state["recent"] = [*self.state["recent"], {"title": title, "status": status, "message": message}][-50:]

    async def run(self):
        try:
            scraper = self.providers[self.state.get("provider", "auto")]
            while self.state["_pending"] and self.state["status"] == "running":
                id = self.state["_pending"][0]
                game = await run_in_threadpool(self.library.game, id)
                title = game["title"] if game else id
                self.state["current_title"] = title
                await self.persist()
                try:
                    if not game:
                        raise ScraperError("El juego ya no está disponible")
                    if game["cover"] and not self.state["overwrite"]:
                        self.state["skipped"] += 1
                        self.record(title, "skipped", "Ya tiene carátula")
                    else:
                        system = await run_in_threadpool(self.library.get_system, game["system_id"])
                        if not system.get("metadata_id"):
                            raise ScraperError("No hay catálogo público configurado para esta consola")
                        if hasattr(scraper, "resolve"):
                            resolved = await scraper.resolve(title, system["metadata_id"])
                        else:
                            results = await scraper.search(title, system["metadata_id"])
                            candidate = (scraper.auto_candidate(title, results, system["metadata_id"])
                                         if hasattr(scraper, "auto_candidate") else best_candidate(title, results))
                            resolved = await scraper.cover(candidate["id"], system["metadata_id"]) if candidate else None
                        if resolved is None:
                            self.state["skipped"] += 1
                            self.record(title, "skipped", "Sin coincidencia inequívoca; busca por título o sube una carátula manual")
                        else:
                            metadata, raw = resolved
                            await self.apply(id, metadata, raw)
                            self.state["updated"] += 1
                            self.record(title, "updated", "Carátula actualizada · " + metadata.get("provider", "libretro"))
                except ScraperError as error:
                    if error.stop_batch:
                        self.state.update(status="paused", message=str(error))
                        self.record(title, "paused", str(error))
                        await self.persist()
                        return
                    self.state["skipped"] += 1
                    self.record(title, "skipped", str(error))
                except Exception:
                    self.state["failed"] += 1
                    self.record(title, "failed", "No se pudo guardar la ficha de este juego")
                self.state["processed"] += 1
                self.state["_pending"].pop(0)
                await self.persist()
            if self.state["status"] == "cancelling":
                self.state.update(status="cancelled", message="Scrape cancelado. Puedes continuar los pendientes.")
            else:
                self.state.update(status="completed", message="Scrape terminado")
            self.state["current_title"] = ""
            await self.persist()
        except asyncio.CancelledError:
            self.state.update(status="interrupted", current_title="", message="Scrape interrumpido. Puedes continuar los pendientes.")
            await self.persist()
        except Exception:
            self.state.update(status="failed", message="El scrape se ha interrumpido. Puedes continuar los pendientes.")
            await self.persist()

    async def shutdown(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await self.task
