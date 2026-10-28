"""Comprueba imágenes públicas de pinball, sin descargar ni transferir ROMs."""
import argparse
import asyncio
from pathlib import Path
import sqlite3
import sys

import httpx


async def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root/'server'))
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    from app.artwork import ArtworkChain
    from app.artwork_catalogs import GameTDB, LaunchBoxCatalog, validate_image
    from app.thumbnails import LibretroThumbnails

    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=root/'data')
    parser.add_argument('--server', help='Comprueba el servidor desplegado en lugar del catálogo local')
    parser.add_argument('--apply', action='store_true', help='Asigna carátulas ausentes y refresca capturas en el servidor')
    args = parser.parse_args()
    thumbnails = LibretroThumbnails(args.data)
    launchbox = LaunchBoxCatalog(args.data)
    chain = ArtworkChain(thumbnails, launchbox, GameTDB(args.data))
    if args.server:
        async with httpx.AsyncClient(base_url=args.server.rstrip('/'), timeout=120) as client:
            response = await client.get('/health'); response.raise_for_status()
            assert response.json()['version'] == '0.10.3', response.json()
            response = await client.get('/api/games', params={'system_id': 'vpinball'}); response.raise_for_status()
            games = [game for game in response.json() if game['system_id'] == 'vpinball']
            assert games, 'No hay mesas de pinball en este servidor'
            for game in games:
                prefix = f'/api/games/{game["id"]}'
                response = await client.get(prefix+'/scrape'); response.raise_for_status()
                candidate = chain.auto_candidate(game['title'], response.json(), 10001)
                if candidate and args.apply and not game['cover_url']:
                    response = await client.post(prefix+'/scrape', json={'provider': 'auto', 'provider_id': candidate['id']})
                    response.raise_for_status()
                    game = response.json()
                if game['cover_url']:
                    response = await client.get(game['cover_url']); response.raise_for_status()
                    validate_image(response.content)
                response = await (client.post(prefix+'/screenshots/refresh') if args.apply else client.get(prefix+'/screenshots'))
                response.raise_for_status()
                images = response.json()['images']
                for item in images:
                    response = await client.get(item['url']); response.raise_for_status()
                    validate_image(response.content)
                print(game['title'], 'carátula:', bool(game['cover_url']), 'capturas:', len(images), flush=True)
        return

    for title in ('Attack from Mars (Bally 1995) g5k 1.3.11.vpx', 'Medieval Madness VPW v1.0.1', 'Black Knight 2000'):
        resolved = await chain.resolve(title, 10001)
        assert resolved, title
        metadata, raw = resolved
        validate_image(raw)
        captures = await chain.screenshots(title, 10001)
        assert captures, title
        for item in captures: validate_image(item['data'])
        print(title, metadata['provider'], 'carátula:', len(raw), 'bytes; capturas:', len(captures), flush=True)
    with sqlite3.connect(launchbox.database) as db:
        for table in ('images', 'captures'):
            count = db.execute(f'SELECT count(*) FROM {table} i JOIN games g ON g.id=i.game WHERE g.system=10001').fetchone()[0]
            print('Pinball', table, count, flush=True)


if __name__ == '__main__': asyncio.run(main())
