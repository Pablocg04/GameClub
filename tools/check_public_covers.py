"""Comprueba búsquedas e imágenes públicas reales sin cuentas ni ROMs."""
import argparse
import asyncio
import io
from pathlib import Path
import sys
from PIL import Image


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    args = parser.parse_args()
    assert args.data.parent.is_dir()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
    from app.thumbnails import LibretroThumbnails
    provider = LibretroThumbnails(args.data)
    for system, title in [(3, '1942.NES'), (3, 'Super Mario Bros. 3'), (3, 'AirFortress'),
                          (26, 'Pac-Man (1982) (Atari, Tod Frye) (PAL) ~.bin'), (26, 'Adventure ~')]:
        results = await provider.search(title, system)
        assert results, (system, title)
        selected = provider.auto_candidate(title, results, system)
        assert selected is not None, (title, results[:3])
        metadata, raw = await provider.cover(selected['id'], system)
        with Image.open(io.BytesIO(raw)) as photo:
            assert photo.width > 50 and photo.height > 50
            dimensions = photo.size
        print(system, title, '=>', selected['description'], dimensions, flush=True)


if __name__ == '__main__': asyncio.run(main())
