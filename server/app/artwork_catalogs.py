"""Índices SQLite de catálogos públicos, construidos en streaming y sin cuentas."""
import asyncio
import io
import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from contextlib import closing
from difflib import SequenceMatcher

import httpx
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from .bulk import normalized
from .scraper import ScraperError
from .thumbnails import base_title, compact_title


LAUNCHBOX_SYSTEMS = {
    'Nintendo Entertainment System': 3, 'Atari 2600': 26,
    'Nintendo Game Boy': 9, 'Nintendo Game Boy Color': 10, 'Nintendo Game Boy Advance': 12,
    'Nintendo GameCube': 13, 'Arcade': 75, 'Nintendo 3DS': 17, 'Nintendo 64': 14,
    'Nintendo DS': 15, 'Sony Playstation 2': 58, 'Sony PlayStation 2': 58,
    'Sony PSP': 61, 'Sony Playstation Vita': 62, 'Sony PlayStation Vita': 62,
    'Sony Playstation': 57, 'Sony PlayStation': 57, 'Super Nintendo Entertainment System': 4,
    'Nintendo Switch': 225, 'Nintendo Wii': 16, 'Nintendo Wii U': 18,
}
GAMETDB_SYSTEMS = {13: 'wii', 16: 'wii', 15: 'ds', 17: '3ds', 18: 'wiiu', 225: 'switch'}
IMAGE_TYPES = {'Box - Front': 0, 'Box - Front - Reconstructed': 1, 'Box - 3D': 2}


def region_rank(region):
    return {'Spain': 0, 'ES': 0, 'Europe': 1, 'PAL': 1, 'EN': 1, 'World': 2,
            'North America': 3, 'USA': 3, 'US': 3, 'NTSC-U': 3, 'Japan': 4, 'JA': 4, 'NTSC-J': 4}.get(region, 6)


def validate_image(raw):
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ScraperError('El catálogo no devolvió una imagen válida') from None
    return raw


class PublicCatalog:
    def __init__(self, data, name, url):
        self.data, self.name, self.url = data, name, url
        self.folder = data / 'artwork'
        self.archive = data / 'artwork-catalogs' / f'{name}.zip'
        self.database = self.folder / f'{name}.sqlite3'
        self.lock = asyncio.Lock()
        self.loaded = False

    def ensure(self):
        if self.database.is_file():
            try:
                with closing(sqlite3.connect(self.database)) as db:
                    if db.execute('PRAGMA user_version').fetchone()[0] == 1:
                        db.execute('SELECT id,system,title FROM games LIMIT 1').fetchone()
                        db.execute('SELECT game,system,title,key,compact FROM titles LIMIT 1').fetchone()
                        db.execute('SELECT game,file,priority,region FROM images LIMIT 1').fetchone()
                        return
            except sqlite3.DatabaseError:
                pass
        self.folder.mkdir(parents=True, exist_ok=True)
        self.archive.parent.mkdir(parents=True, exist_ok=True)
        if self.archive.exists():
            try:
                with zipfile.ZipFile(self.archive) as cached:
                    valid = any(name.lower().endswith('.xml') and (self.name != 'launchbox' or name == 'Metadata.xml')
                                for name in cached.namelist())
            except (zipfile.BadZipFile, OSError):
                valid = False
            if not valid: self.archive.unlink()
        if not self.archive.exists():
            temporary = self.archive.with_suffix('.part')
            try:
                with httpx.Client(follow_redirects=True, timeout=240) as client, client.stream('GET', self.url) as response:
                    response.raise_for_status()
                    size = 0
                    with temporary.open('wb') as output:
                        for chunk in response.iter_bytes(1024 * 1024):
                            size += len(chunk)
                            if size > 256 * 1024 * 1024:
                                raise ValueError('Catálogo demasiado grande')
                            output.write(chunk)
                temporary.replace(self.archive)
            finally:
                temporary.unlink(missing_ok=True)
        temporary = self.database.with_suffix('.part')
        temporary.unlink(missing_ok=True)
        try:
            with closing(sqlite3.connect(temporary)) as db, db, zipfile.ZipFile(self.archive) as archive:
                db.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
                    CREATE TABLE games (id TEXT PRIMARY KEY, system INTEGER, title TEXT);
                    CREATE TABLE titles (game TEXT, system INTEGER, title TEXT, key TEXT, compact TEXT);
                    CREATE TABLE images (game TEXT, file TEXT, priority INTEGER, region INTEGER);''')
                xml = next(item for item in archive.infolist() if item.filename.lower().endswith('.xml')
                           and (self.name != 'launchbox' or item.filename == 'Metadata.xml'))
                if xml.file_size > 1024 * 1024 * 1024:
                    raise ValueError('XML demasiado grande')
                with archive.open(xml) as stream:
                    self.parse(db, stream)
                db.executescript('''CREATE INDEX titles_system ON titles(system);
                    CREATE INDEX titles_exact ON titles(system,compact);
                    CREATE INDEX images_game ON images(game,priority,region);
                    PRAGMA user_version=1;''')
                if not db.execute('SELECT 1 FROM games LIMIT 1').fetchone():
                    raise ValueError('Catálogo vacío')
            temporary.replace(self.database)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def records(stream):
        depth, root = 0, None
        for event, element in ET.iterparse(stream, events=('start', 'end')):
            if event == 'start':
                depth += 1
                if root is None: root = element
                continue
            if depth == 2:
                yield element
                root.clear()
            depth -= 1

    @staticmethod
    def add_title(db, game, system, title):
        title = base_title(title)
        if title:
            db.execute('INSERT INTO titles VALUES (?,?,?,?,?)', (game, system, title, normalized(title), compact_title(title)))

    async def load(self):
        async with self.lock:
            if not self.loaded:
                try:
                    await run_in_threadpool(self.ensure)
                except (httpx.HTTPError, OSError, ValueError, zipfile.BadZipFile, ET.ParseError, sqlite3.DatabaseError, StopIteration):
                    raise ScraperError(f'No se pudo preparar el catálogo público {self.name}', stop_batch=True) from None
                self.loaded = True

    def find(self, title, system):
        query = normalized(base_title(title))
        compact = compact_title(query)
        if not compact: return []
        with closing(sqlite3.connect(self.database)) as db:
            rows = db.execute('''SELECT t.game,g.title,t.title,t.key FROM titles t JOIN games g ON g.id=t.game
                WHERE t.system=? AND t.compact=? AND EXISTS(SELECT 1 FROM images WHERE game=g.id)''', (system, compact)).fetchall()
            if not rows:
                tokens = sorted(set(query.split()), key=len, reverse=True)[:3]
                clause = ' OR '.join('t.key LIKE ?' for _ in tokens)
                rows = db.execute(f'''SELECT t.game,g.title,t.title,t.key FROM titles t JOIN games g ON g.id=t.game
                    WHERE t.system=? AND ({clause}) AND EXISTS(SELECT 1 FROM images WHERE game=g.id) LIMIT 1500''',
                    (system, *(f'%{token}%' for token in tokens))).fetchall()
        found = {}
        for game, canonical, alias, key in rows:
            score = 1.0 if compact_title(key) == compact else SequenceMatcher(None, query, key).ratio()
            if score < .7: continue
            if game not in found or score > found[game]['match_score']:
                found[game] = {'id': game, 'title': canonical, 'match_title': alias,
                    'description': f'{canonical} · Carátula', 'match_score': score}
        return sorted(found.values(), key=lambda item: (-item['match_score'], item['title'], item['id']))[:30]

    def details(self, game, system):
        with closing(sqlite3.connect(self.database)) as db:
            title = db.execute('SELECT title FROM games WHERE id=? AND system=?', (game, system)).fetchone()
            images = db.execute('SELECT file FROM images WHERE game=? ORDER BY priority,region,file', (game,)).fetchall() if title else []
        return (title[0] if title else None), [image[0] for image in images]

    async def search(self, title, system):
        await self.load()
        return await run_in_threadpool(self.find, title, system)

    async def title(self, game, system):
        await self.load()
        return (await run_in_threadpool(self.details, game, system))[0]

    async def cover(self, game, system):
        await self.load()
        title, images = await run_in_threadpool(self.details, game, system)
        if not title: raise ScraperError('El resultado del catálogo ya no está disponible')
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            for file in images:
                try:
                    async with client.stream('GET', self.image_url(file)) as response:
                        if response.status_code == 404: continue
                        response.raise_for_status()
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            raw.extend(chunk)
                            if len(raw) > 10 * 1024 * 1024: raise ScraperError('Imagen demasiado grande')
                    validate_image(bytes(raw))
                    return {'title': title, 'description': '', 'provider': self.provider}, bytes(raw)
                except httpx.HTTPError:
                    raise ScraperError(f'No se pudo descargar la imagen de {self.provider}', stop_batch=True) from None
                except ScraperError:
                    continue
        raise ScraperError(f'No hay carátula descargable en {self.provider}')


class LaunchBoxCatalog(PublicCatalog):
    provider = 'launchbox'
    def __init__(self, data):
        super().__init__(data, 'launchbox', 'https://gamesdb.launchbox-app.com/Metadata.zip')

    def parse(self, db, stream):
        systems = {}
        for element in self.records(stream):
            game = element.findtext('DatabaseID')
            if element.tag == 'Game':
                system = LAUNCHBOX_SYSTEMS.get(element.findtext('Platform'))
                title = element.findtext('Name')
                if not system or not game or not title: continue
                systems[game] = system
                db.execute('INSERT OR REPLACE INTO games VALUES (?,?,?)', (game, system, title))
                self.add_title(db, game, system, title)
            elif element.tag == 'GameAlternateName' and game in systems:
                self.add_title(db, game, systems[game], element.findtext('AlternateName') or '')
            elif element.tag == 'GameImage' and game in systems:
                kind, file = element.findtext('Type'), element.findtext('FileName') or ''
                if kind in IMAGE_TYPES and re.fullmatch(r'[a-zA-Z0-9-]+\.(?:jpg|png|webp)', file):
                    db.execute('INSERT INTO images VALUES (?,?,?,?)',
                        (game, file, IMAGE_TYPES[kind], region_rank(element.findtext('Region'))))

    def image_url(self, file):
        return 'https://images.launchbox-app.com/' + file

    async def search(self, title, system):
        if system not in LAUNCHBOX_SYSTEMS.values(): return []
        return await super().search(title, system)


class GameTDBCatalog(PublicCatalog):
    provider = 'gametdb'
    def __init__(self, data, family):
        self.family = family
        super().__init__(data, family, f'https://www.gametdb.com/{family}tdb.zip')

    def parse(self, db, stream):
        for element in self.records(stream):
            if element.tag != 'game': continue
            game = element.findtext('id') or ''
            if not re.fullmatch(r'[A-Z0-9]{4,8}', game): continue
            if self.family == 'wii':
                system = 13 if (element.findtext('type') or '').lower() == 'gamecube' or game.startswith('G') else 16
            else:
                system = {'ds': 15, '3ds': 17, 'wiiu': 18, 'switch': 225}[self.family]
            locales = {locale.get('lang'): locale.findtext('title') for locale in element.findall('locale') if locale.findtext('title')}
            title = locales.get('EN') or locales.get('ES') or base_title(element.get('name', ''))
            db.execute('INSERT OR REPLACE INTO games VALUES (?,?,?)', (game, system, title))
            for alias in set([title, *locales.values(), base_title(element.get('name', ''))]):
                self.add_title(db, game, system, alias)
            # ES/EN para PAL; no atribuir una portada europea al identificador USA/Japón.
            region = element.findtext('region') or ''
            languages = ['ES', 'EN', 'US', 'JA'] if region in {'PAL', 'Europe'} else ['US', 'EN', 'ES', 'JA']
            if region in {'NTSC-J', 'Japan'}: languages = ['JA', 'US', 'EN', 'ES']
            for order, language in enumerate(languages):
                extension = 'png' if self.family == 'wii' else 'jpg'
                db.execute('INSERT INTO images VALUES (?,?,?,?)', (game, f'{language}/{game}.{extension}', 0, order))

    def image_url(self, file):
        return f'https://art.gametdb.com/{self.family}/cover/{file}'

    def find(self, title, system):
        results = super().find(title, system)
        for result in results:
            code = result['id']
            result['region_rank'] = ({'P': 1, 'D': 1, 'F': 1, 'I': 1, 'S': 0, 'E': 3, 'J': 4}.get(code[3], 6)
                                     if self.family != 'switch' and len(code) >= 4 else 6)
        return sorted(results, key=lambda item: (-item['match_score'], item['region_rank'], item['id']))

    async def cover(self, game, system):
        try:
            return await super().cover(game, system)
        except ScraperError as error:
            if error.stop_batch: raise
            title = await self.title(game, system)
            if not title: raise
            # Algunas variantes regionales tienen ficha pero no imagen: probar la misma edición del juego en otra región.
            for result in await self.search(title, system):
                if result['id'] == game or compact_title(result['title']) != compact_title(title): continue
                try:
                    return await super().cover(result['id'], system)
                except ScraperError as alternative:
                    if alternative.stop_batch: raise
            raise error


class GameTDB:
    def __init__(self, data):
        self.catalogs = {family: GameTDBCatalog(data, family) for family in set(GAMETDB_SYSTEMS.values())}

    async def search(self, title, system):
        family = GAMETDB_SYSTEMS.get(system)
        return await self.catalogs[family].search(title, system) if family else []

    async def title(self, game, system):
        family = GAMETDB_SYSTEMS.get(system)
        return await self.catalogs[family].title(game, system) if family else None

    async def cover(self, game, system):
        family = GAMETDB_SYSTEMS.get(system)
        if not family: raise ScraperError('GameTDB no cubre esta consola')
        return await self.catalogs[family].cover(game, system)
