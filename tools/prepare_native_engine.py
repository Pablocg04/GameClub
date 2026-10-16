"""Descarga dependencias SDL fijadas para el reproductor nativo de GameClub."""
import argparse
import hashlib
import io
import zipfile
from pathlib import Path
import httpx

SDL_VERSION = "3.4.18"
PACKAGES = {
    "android": ("SDL3-devel-3.4.18-android.zip", "e09e4d6593335d089ba124375e8b8abd0fd75173dffcd2c17012b45af121d4e9"),
    "windows": ("SDL3-devel-3.4.18-VC.zip", "78d84602ae616cfe26b33a73b7d3b9b6b56e8a6650e53d92c9c6ca938f747acd"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    assert root.parent.is_dir()
    root.mkdir(exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=180) as client:
        for platform, (name, digest) in PACKAGES.items():
            target = root / platform
            if target.exists():
                continue
            response = client.get(f"https://github.com/libsdl-org/SDL/releases/download/release-{SDL_VERSION}/{name}")
            response.raise_for_status()
            assert hashlib.sha256(response.content).hexdigest() == digest
            target.mkdir()
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                assert all((target / entry).resolve().is_relative_to(target) for entry in archive.namelist())
                archive.extractall(target)
                print(platform, archive.namelist()[:30], flush=True)
        header = root / "libretro.h"
        if not header.exists():
            response = client.get("https://raw.githubusercontent.com/libretro/RetroArch/v1.22.2/libretro-common/include/libretro.h")
            response.raise_for_status()
            header.write_bytes(response.content)


if __name__ == "__main__":
    main()
