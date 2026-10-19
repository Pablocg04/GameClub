"""Verifica carátulas en el servidor; opcionalmente asigna dos que estén ausentes."""
import argparse
import io
import sys
import httpx
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', required=True)
    parser.add_argument('--apply-missing', action='store_true')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    with httpx.Client(base_url=args.server, timeout=120) as client:
        assert client.get('/health').raise_for_status().json()['version'] == '0.9.0'
        settings = client.get('/api/settings').raise_for_status().json()
        assert settings['scrape_provider'] == 'auto'
        assert settings['scrape_order'] == ['libretro', 'launchbox', 'gametdb']
        assert all(not p['requires_key'] and not p['requires_account'] for p in settings['providers'])
        for system, query in [('nes', '1942'), ('atari2600', 'Pac-Man')]:
            games = client.get('/api/games', params={'system_id': system, 'q': query}).raise_for_status().json()
            game = next(game for game in games if game['title'].strip(' ~').casefold() == query.casefold())
            results = client.get(f'/api/games/{game["id"]}/scrape').raise_for_status().json()
            assert results and results[0]['title'].casefold() == query.casefold(), results[:2]
            print(system, game['title'], '=>', results[0]['description'], flush=True)
            if args.apply_missing and not game['cover_url']:
                updated = client.post(f'/api/games/{game["id"]}/scrape', json={'provider_id': results[0]['id']}).raise_for_status().json()
                assert updated['provider'] == 'libretro'
                image = client.get(updated['cover_url']).raise_for_status()
                with Image.open(io.BytesIO(image.content)) as photo:
                    assert photo.width > 50 and photo.height > 50
                    print('Carátula guardada:', photo.size, flush=True)
        systems = client.get('/api/systems', params={'include_empty': True}).raise_for_status().json()
        print('Consolas:', [(s['id'], s['metadata_id'], s['game_count']) for s in systems if s['id'] in {'nes', 'atari2600'}], flush=True)


if __name__ == '__main__': main()
