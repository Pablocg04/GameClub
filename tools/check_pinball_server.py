"""Verifica un despliegue pinball mediante lecturas API, sin subir mesas ni ROMs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', required=True)
    parser.add_argument('--token', default='')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    expected = json.loads((Path(__file__).resolve().parents[1]/'server/app/pinball_runtime.json').read_text(encoding='utf-8'))
    headers = {'Authorization': f'Bearer {args.token}'} if args.token else {}
    with httpx.Client(base_url=args.server, headers=headers, timeout=120) as client:
        health = client.get('/health').raise_for_status().json()
        assert health['status'] == 'ok' and health['version'] == '0.9.0', health
        systems = client.get('/api/systems', params={'include_empty': True}).raise_for_status().json()
        system = next(system for system in systems if system['id'] == 'vpinball')
        assert {'.zip', '.vpxz', '.vpx'} <= set(system['extensions'])
        info = client.get('/api/player/pinball').raise_for_status().json()
        assert info == expected, 'El registro remoto de VPX no coincide con el fijado'
        for platform, entry in info['platforms'].items():
            digest, size = hashlib.sha256(), 0
            with client.stream('GET', f'/api/player/pinball/{platform}') as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(1024*1024):
                    digest.update(chunk)
                    size += len(chunk)
            assert size == entry['size'] and digest.hexdigest() == entry['sha256'], platform
            print(f'{platform}: {size} bytes, SHA-256 correcto', flush=True)
        games = client.get('/api/games', params={'system_id': 'mame', 'category': 'pinball'}).raise_for_status().json()
        assert all(game['system_id'] == 'mame' and game['category'] == 'pinball' for game in games)
        print('Servidor', health, '| mesas VPX:', system['game_count'], '| pinballs MAME:', len(games), flush=True)


if __name__ == '__main__':
    main()
