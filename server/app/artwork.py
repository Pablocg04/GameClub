"""Búsqueda y descarga en orden: Libretro, LaunchBox y GameTDB."""
from .artwork_catalogs import validate_image
from .scraper import ScraperError


class ArtworkChain:
    names = {'libretro': 'Libretro', 'launchbox': 'LaunchBox', 'gametdb': 'GameTDB'}

    def __init__(self, libretro, launchbox, gametdb):
        self.libretro = libretro
        self.sources = {'libretro': libretro, 'launchbox': launchbox, 'gametdb': gametdb}

    def require_configuration(self):
        pass

    def auto_candidate(self, title, results, system):
        adjusted = [{**item, 'title': item.get('match_title', item['title'])} for item in results]
        candidate = self.libretro.auto_candidate(title, adjusted, system)
        return next((item for item in results if candidate and item['id'] == candidate['id']), None)

    async def _search(self, name, source, title, system):
        if name == 'libretro':
            return await source.search(title, system, kinds=('Named_Boxarts',))
        return await source.search(self.libretro.query(title, system), system)

    def stamp(self, name, results):
        return [{**item, 'id': f'{name}-{item["id"]}', 'provider': name,
                 'description': f'{self.names[name]} · {item["description"]}'} for item in results]

    async def search(self, title, system):
        suggestions, errors = [], []
        for name, source in self.sources.items():
            try:
                results = self.stamp(name, await self._search(name, source, title, system))
                if self.auto_candidate(title, results, system): return results
                if results and not suggestions: suggestions = results
            except ScraperError as error:
                if error.stop_batch: errors.append(str(error))
        if suggestions: return suggestions
        if errors: raise ScraperError('; '.join(errors), stop_batch=True)
        return []

    async def resolve(self, title, system):
        """El lote prueba también la descarga antes de dar una fuente por válida."""
        errors = []
        for name, source in self.sources.items():
            try:
                results = await self._search(name, source, title, system)
                candidate = self.auto_candidate(title, results, system)
                if candidate:
                    metadata, raw = await source.cover(candidate['id'], system)
                    validate_image(raw)
                    return {**metadata, 'provider': name}, raw
            except ScraperError as error:
                if error.stop_batch: errors.append(str(error))
        if errors: raise ScraperError('; '.join(errors), stop_batch=True)
        return None

    async def cover(self, id, system):
        # Los identificadores Libretro sin prefijo de versiones anteriores siguen funcionando.
        name, _, original = id.partition('-')
        if name not in self.sources: name, original = 'libretro', id
        source = self.sources[name]
        try:
            metadata, raw = await source.cover(original, system)
            validate_image(raw)
            return {**metadata, 'provider': name}, raw
        except ScraperError as original_error:
            title = await source.title(original, system)
            if not title: raise original_error
            later = list(self.sources).index(name) + 1
            for next_name in list(self.sources)[later:]:
                following = self.sources[next_name]
                try:
                    results = await self._search(next_name, following, title, system)
                    candidate = self.auto_candidate(title, results, system)
                    if not candidate: continue
                    metadata, raw = await following.cover(candidate['id'], system)
                    validate_image(raw)
                    return {**metadata, 'provider': next_name}, raw
                except ScraperError:
                    continue
            raise original_error
