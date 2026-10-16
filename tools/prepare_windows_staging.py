"""Prepara una compilación Windows independiente de un ejecutable en uso."""
import argparse
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / "client"
    args.destination.mkdir(parents=True, exist_ok=True)
    for folder in ("lib", "platform-config", "native", "assets"):
        shutil.copytree(source / folder, args.destination / folder, dirs_exist_ok=True)
    for file in ("pubspec.yaml", "pubspec.lock", "analysis_options.yaml", "bootstrap.ps1"):
        shutil.copy2(source / file, args.destination / file)
    print(f"Proyecto de compilación preparado: {args.destination}")


if __name__ == "__main__":
    main()
