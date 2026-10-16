"""Importa solo metadatos del MAMEUI histórico, sin ROMs ni ejecutables."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "server"))
    from app.arcade import ArcadeCatalog
    result = subprocess.run([str(args.executable.resolve()), "-listxml"], capture_output=True, check=True, timeout=120)
    catalog = ArcadeCatalog.parse(result.stdout)
    assert len(catalog) > 7000
    target = root / "server" / "app" / "native_mame0130.json.gz"
    target.write_bytes(gzip.compress(json.dumps(catalog, separators=(",", ":")).encode(), mtime=0))
    print(f"Catálogo histórico: {len(catalog)} máquinas, {target.stat().st_size} bytes")


if __name__ == "__main__":
    main()
