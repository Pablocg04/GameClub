"""Extrae nombres públicos de juegos del ejecutable MAMEUI para buscar imágenes."""
import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    document = ET.fromstring(subprocess.check_output([str(args.executable), "-listxml"], timeout=120))
    names = {game.get("name"): game.findtext("description") for game in document
             if game.tag in {"game", "machine"} and game.get("name") and game.findtext("description")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    print(f"Catálogo extraído: {len(names)} entradas, versión {document.get('build')}")


if __name__ == "__main__":
    main()
