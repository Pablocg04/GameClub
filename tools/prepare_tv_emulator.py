"""Prepara un AVD Google TV aislado en una carpeta temporal indicada explícitamente."""
import argparse
import hashlib
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    assert root.parent.is_dir(), "La carpeta temporal padre debe existir"
    root.mkdir(exist_ok=True)
    repository = "https://dl.google.com/android/repository/sys-img/google-tv/"
    image = root / "image"
    if not (image / "x86_64" / "system.img").is_file():
        response = httpx.get(repository + "sys-img2-3.xml", timeout=60)
        response.raise_for_status()
        catalog = ET.fromstring(response.content)
        package = next(p for p in catalog.iter("remotePackage") if p.get("path") == "system-images;android-36;google-tv;x86_64")
        archive = next(package.iter("complete"))
        name, expected = archive.findtext("url"), int(archive.findtext("size"))
        checksum = archive.find("checksum")
        algorithm = checksum.get("type", "sha1")
        dest = root / name
        if not dest.is_file() or dest.stat().st_size != expected:
            print(f"Descargando Google TV: {expected / 1024 / 1024:.0f} MiB", flush=True)
            with httpx.stream("GET", repository + name, timeout=120) as download, dest.with_suffix(".part").open("wb") as output:
                download.raise_for_status()
                count = 0
                last = 0
                for chunk in download.iter_bytes(1024 * 1024):
                    count += len(chunk)
                    output.write(chunk)
                    if count - last > 100 * 1024 * 1024:
                        print(f"  {count / 1024 / 1024:.0f} MiB", flush=True)
                        last = count
            assert count == expected, "Descarga incompleta"
            dest.with_suffix(".part").replace(dest)
        digest = hashlib.new(algorithm)
        with dest.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        assert digest.hexdigest().lower() == checksum.text.lower(), "Checksum incorrecto"
        image.mkdir(exist_ok=True)
        with zipfile.ZipFile(dest) as source:
            assert all((image / name).resolve().is_relative_to(image) for name in source.namelist())
            source.extractall(image)
    assert (image / "x86_64" / "system.img").is_file()
    avds = root / "avds"
    avd = avds / "GameClubTV.avd"
    avd.mkdir(parents=True, exist_ok=True)
    (avds / "GameClubTV.ini").write_text(f"avd.ini.encoding=UTF-8\npath={avd}\ntarget=android-36\n", encoding="utf-8")
    configuration = {
        "avd.ini.encoding": "UTF-8", "AvdId": "GameClubTV", "avd.ini.displayname": "GameClub TV Test",
        "abi.type": "x86_64", "hw.cpu.arch": "x86_64", "hw.cpu.ncore": "2",
        "image.sysdir.1": str(image / "x86_64") + "\\", "tag.id": "google-tv", "tag.display": "Google TV",
        "hw.device.name": "tv_1080p", "hw.device.manufacturer": "Google", "hw.ramSize": "2048",
        "hw.lcd.width": "1280", "hw.lcd.height": "720", "hw.lcd.density": "160",
        "hw.initialOrientation": "landscape", "hw.dPad": "yes", "hw.keyboard": "yes", "hw.mainKeys": "yes",
        "hw.gpu.enabled": "yes", "hw.gpu.mode": "swiftshader_indirect", "disk.dataPartition.size": "4G",
        "showDeviceFrame": "no", "fastboot.forceColdBoot": "yes", "PlayStore.enabled": "false",
        "hw.audioInput": "no", "hw.sensors.orientation": "no", "hw.sensors.proximity": "no",
    }
    (avd / "config.ini").write_text("".join(f"{key}={value}\n" for key, value in configuration.items()), encoding="utf-8")
    print(f"AVD listo. ANDROID_AVD_HOME={avds}", flush=True)


if __name__ == "__main__":
    main()
