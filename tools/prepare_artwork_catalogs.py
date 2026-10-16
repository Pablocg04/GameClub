"""Prepara índices públicos reutilizables en PC/Raspberry; no contiene ROMs."""
import sys
from pathlib import Path


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root/'server'))
    from app.artwork_catalogs import LaunchBoxCatalog, GameTDB
    for catalog in [LaunchBoxCatalog(root/'data'), *GameTDB(root/'data').catalogs.values()]:
        print('Preparando', catalog.name, flush=True)
        catalog.ensure()
        print(catalog.database, catalog.database.stat().st_size, flush=True)


if __name__ == '__main__': main()
