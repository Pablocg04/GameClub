import asyncio
import hashlib
import json
import re
import time
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote

import httpx

from .bulk import best_candidate, normalized
from .scraper import ScraperError


FOLDERS = {
    3: "Nintendo - Nintendo Entertainment System", 26: "Atari - 2600",
    9: "Nintendo - Game Boy", 10: "Nintendo - Game Boy Color",
    12: "Nintendo - Game Boy Advance", 4: "Nintendo - Super Nintendo Entertainment System",
    15: "Nintendo - Nintendo DS", 14: "Nintendo - Nintendo 64",
    17: "Nintendo - Nintendo 3DS", 13: "Nintendo - GameCube",
    16: "Nintendo - Wii", 18: "Nintendo - Wii U", 75: "MAME",
    57: "Sony - PlayStation", 58: "Sony - PlayStation 2",
    61: "Sony - PlayStation Portable", 62: "Sony - PlayStation Vita",
}


def base_title(title):
    title = re.sub(r"\.(?:nes|unf|unif|bin|a26|rom|zip|7z|nds|gb|gbc|gba|sfc|smc|png)$", "", title, flags=re.I)
    title = re.sub(r"\s*[\[(].*?[\])]", "", title)
    title = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", title.replace("_", " "))
    return re.sub(r"\s+", " ", title).strip(" ~")


def compact_title(title):
    return normalized(title).replace(" ", "")


class ImageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        name = unquote(href)
        if name.endswith(".png") and not any(c in name for c in "/\\\x00") and name not in {".", ".."}:
            self.names.add(name)


class LibretroThumbnails:
    base = "https://thumbnails.libretro.com/"

    def __init__(self, data):
        self.root = data / "thumbnails"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = asyncio.Lock()
        self.indices = {}
        self.entries = {}
        self.last_request = 0.0
        try:
            self.mame_names = json.loads((data / "mame_names.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self.mame_names = {}

    def require_configuration(self):
        pass  # Catálogo público: no necesita cuenta ni claves.

    def query(self, title, system):
        title = Path(title).stem if title.lower().endswith((".zip", ".7z", ".nds")) else title
        return self.mame_names.get(title, title) if system == 75 else title

    async def request(self, client, url, limit):
        await asyncio.sleep(max(0, .5 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        try:
            async with client.stream("GET", url) as response:
                if response.status_code == 404:
                    raise ScraperError("No hay imágenes disponibles para este recurso")
                response.raise_for_status()
                result = bytearray()
                async for chunk in response.aiter_bytes():
                    result.extend(chunk)
                    if len(result) > limit:
                        raise ScraperError("La respuesta de miniaturas supera el tamaño permitido", stop_batch=True)
                return bytes(result)
        except httpx.HTTPError:
            raise ScraperError("No se pudo conectar con el catálogo público de Libretro. Inténtalo más tarde.", stop_batch=True) from None

    async def index(self, client, system, kind):
        if system not in FOLDERS:
            raise ScraperError("Libretro no tiene un catálogo configurado para esta consola")
        key = (system, kind)
        if key in self.indices:
            return self.indices[key]
        cache = self.root / f"{system}-{kind}.json"
        names = None
        if cache.exists() and time.time() - cache.stat().st_mtime < 7 * 86400:
            try:
                names = json.loads(cache.read_text(encoding="utf-8"))
            except ValueError:
                pass
        if names is None:
            url = self.base + quote(FOLDERS[system], safe="") + f"/{kind}/"
            page = await self.request(client, url, 12 * 1024 * 1024)
            parser = ImageLinks()
            parser.feed(page.decode("utf-8", errors="replace"))
            names = sorted(parser.names)
            if not names:
                raise ScraperError("El catálogo de imágenes no devolvió una lista válida", stop_batch=True)
            temporary = cache.with_suffix(".part")
            temporary.write_text(json.dumps(names), encoding="utf-8")
            temporary.replace(cache)
        self.indices[key] = names
        return names

    @staticmethod
    def token(system, kind, name):
        return hashlib.sha256(f"{system}/{kind}/{name}".encode()).hexdigest()[:24]

    @staticmethod
    def region_order(name):
        return next((order for order, region in enumerate(("Spain", "Europe", "World", "USA|US", "Japan"))
                     if re.search(r"\((?:" + region + r")(?:\b|\))", name)), 6)

    async def search(self, title, system_id, kinds=("Named_Boxarts", "Named_Snaps")):
        if system_id not in FOLDERS:
            raise ScraperError("No hay catálogo público de Libretro configurado para esta consola")
        original = self.query(title, system_id)
        query = normalized(base_title(original))
        if not query:
            return []
        async with self.lock, httpx.AsyncClient(timeout=45) as client:
            for kind in kinds:
                try:
                    names = await self.index(client, system_id, kind)
                except ScraperError as error:
                    if error.stop_batch:
                        raise
                    continue
                if (system_id, kind) not in self.entries:
                    self.entries[system_id, kind] = [(name, base_title(name[:-4]), normalized(base_title(name[:-4])), self.region_order(name)) for name in names]
                ranked = []
                tokens = set(query.split())
                for name, clean, candidate, region in self.entries[system_id, kind]:
                    compact_match = compact_title(candidate) == compact_title(query)
                    if not compact_match and not tokens.intersection(candidate.split()):
                        continue
                    score = 1.0 if compact_match else SequenceMatcher(None, query, candidate).ratio()
                    if candidate == query or score >= .7 or query in candidate:
                        ranked.append((score, region, name, clean))
                def penalty(name):
                    special = re.search(r"\b(Demo|Proto|Beta|Kiosk|Sample)\b", name, re.I)
                    return int(bool(special) and not re.search(r"\b(Demo|Proto|Beta|Kiosk|Sample)\b", original, re.I))
                ranked.sort(key=lambda item: (-item[0], penalty(item[2]), item[1], item[2]))
                if ranked:
                    return [{"id": self.token(system_id, kind, name), "title": clean,
                             "description": name[:-4] + (" · Carátula" if kind == "Named_Boxarts" else " · Captura"),
                             "provider": "libretro", "region_rank": region, "match_score": score}
                            for score, region, name, clean in ranked[:30]]
            return []

    def auto_candidate(self, title, results, system_id):
        target = base_title(self.query(title, system_id))
        # Distintas regiones del mismo título comparten juego; preferir España/Europa.
        unique = {}
        for result in results:
            unique.setdefault(compact_title(result["title"]), result)
        exact = unique.get(compact_title(target))
        if exact is not None:
            return exact
        return best_candidate(target, list(unique.values()))

    async def cover(self, game_id, system_id):
        async with self.lock, httpx.AsyncClient(timeout=45) as client:
            for kind in ("Named_Boxarts", "Named_Snaps"):
                try:
                    names = await self.index(client, system_id, kind)
                except ScraperError as error:
                    if error.stop_batch:
                        raise
                    continue
                name = next((name for name in names if self.token(system_id, kind, name) == game_id), None)
                if name is None:
                    continue
                url = self.base + quote(FOLDERS[system_id], safe="") + f"/{kind}/" + quote(name, safe="")
                image = await self.request(client, url, 10 * 1024 * 1024)
                return {"title": base_title(name[:-4]), "description": "", "provider": "libretro"}, image
            raise ScraperError("El resultado de Libretro ya no está disponible; repite la búsqueda")

    async def title(self, game_id, system_id):
        async with self.lock, httpx.AsyncClient(timeout=45) as client:
            for kind in ('Named_Boxarts', 'Named_Snaps'):
                try:
                    names = await self.index(client, system_id, kind)
                except ScraperError:
                    continue
                name = next((name for name in names if self.token(system_id, kind, name) == game_id), None)
                if name: return base_title(name[:-4])
        return None

    async def screenshots(self, title, system_id):
        results=await self.search(title,system_id,kinds=("Named_Snaps",))
        candidate=self.auto_candidate(title,results,system_id)
        if candidate is None:
            return []
        images=[]
        seen=set()
        for item in results:
            if normalized(item["title"])!=normalized(candidate["title"]):
                continue
            metadata,data=await self.cover(item["id"],system_id)
            digest=hashlib.sha256(data).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            images.append({"source_id":item["id"],"label":item["description"],"data":data})
            if len(images)>=3:
                break
        return images
