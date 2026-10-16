"""Descargas reales de las fuentes y cadena forzada solo dentro de esta prueba local."""
import asyncio
import argparse
from pathlib import Path
import sys


async def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=root/'data')
    args = parser.parse_args()
    sys.path.insert(0, str(root/'server'))
    from app.artwork import ArtworkChain
    from app.artwork_catalogs import LaunchBoxCatalog, GameTDB, validate_image
    from app.thumbnails import LibretroThumbnails
    libretro, launchbox, gametdb = LibretroThumbnails(args.data), LaunchBoxCatalog(args.data), GameTDB(args.data)
    chain = ArtworkChain(libretro, launchbox, gametdb)
    for title, system in [('1942', 3), ('Super Mario Bros. 3', 3), ('Pac-Man', 26)]:
        metadata, raw = await chain.resolve(title, system)
        print('CADENA', title, metadata['provider'], len(validate_image(raw)), flush=True)
    for provider, title, system in [(launchbox, 'Super Mario Bros. 3', 3), (launchbox, 'Pac-Man', 26),
                                    (gametdb, 'Super Mario Galaxy', 16), (gametdb, 'Mario Kart DS', 15)]:
        results = await provider.search(title, system)
        selected = chain.auto_candidate(title, results, system)
        assert selected, (title, results[:2])
        metadata, raw = await provider.cover(selected['id'], system)
        print('FUENTE', title, metadata['provider'], len(validate_image(raw)), flush=True)
    async def empty(*args, **kwargs): return []
    libretro.search = empty
    assert (await chain.resolve('Super Mario Bros. 3', 3))[0]['provider'] == 'launchbox'
    launchbox.search = empty
    assert (await chain.resolve('Super Mario Galaxy', 16))[0]['provider'] == 'gametdb'
    print('Fallback real hasta LaunchBox y hasta GameTDB correcto; no se han transferido ROMs.', flush=True)


if __name__ == '__main__': asyncio.run(main())
