"""Fija binarios nativos oficiales de Libretro y sus huellas para el servidor."""
import concurrent.futures
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile
import shutil
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--consoles-only", action="store_true", help="Añade NES y Atari 2600 conservando los motores arcade fijados")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = root / "data" / "native-cores" / "v1"
    destination.mkdir(parents=True, exist_ok=True)
    platforms = {
        **{f"android-{abi}": (f"android/latest/{abi}", "_libretro_android.so")
           for abi in ("arm64-v8a", "armeabi-v7a", "x86_64")},
        "windows-x86_64": ("windows/x86_64/latest", "_libretro.dll"),
    }
    registry = root / "server" / "app" / "native_cores.json"
    metadata = json.loads(registry.read_text(encoding="utf-8"))

    def fetch(item):
        platform, core = item
        folder, suffix = platforms[platform]
        binary = ("mame" if core == "mamearcade" and platform == "windows-x86_64" else core) + suffix
        url = f"https://buildbot.libretro.com/nightly/{folder}/{binary}.zip"
        target = destination / platform / f"{core}.zip"
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            with httpx.Client(follow_redirects=True, timeout=240) as client:
                response = client.get(url)
                response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                assert binary in archive.namelist()
                archive.testzip()
            target.write_bytes(response.content)
        data = target.read_bytes()
        pinned = metadata.get(platform, {}).get(core)
        if pinned:
            assert len(data) == pinned["size"] and hashlib.sha256(data).hexdigest() == pinned["sha256"], f"Motor distinto del fijado: {platform}/{core}"
            return platform, core, pinned
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            library = archive.read(binary)
        print(platform, core, len(data), flush=True)
        return platform, core, {"source": url, "sha256": hashlib.sha256(data).hexdigest(),
                                "size": len(data), "binary": binary,
                                "binary_size": len(library), "binary_sha256": hashlib.sha256(library).hexdigest()}

    cores = ("nestopia", "stella") if args.consoles_only else ("mame2003_plus", "mame2003", "fbneo", "mamearcade", "nestopia", "stella")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for platform, core, entry in executor.map(fetch, [(platform, core) for platform in platforms
                                                         for core in cores]):
            metadata.setdefault(platform, {})[core] = entry
    for entries in metadata.values(): entries.pop("fceumm", None)
    registry.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    # Las consolas incluyen sus motores en las apps: no dependen de actualizar el servidor.
    assets = root / "client" / "assets"
    bundled = {platform: {core: entries[core] for core in ("nestopia", "stella")} for platform, entries in metadata.items()}
    (assets / "native_console_cores.json").write_text(json.dumps({"version": "console-1", "platforms": bundled}, indent=2) + "\n", encoding="utf-8")
    for platform, entries in bundled.items():
        folder = assets / "native-cores" / platform
        folder.mkdir(parents=True, exist_ok=True)
        for core in entries:
            shutil.copy2(destination / platform / f"{core}.zip", folder / f"{core}.zip")
        for previous in folder.glob("*.zip"):
            if previous.stem not in entries: previous.unlink()


if __name__ == "__main__":
    main()
