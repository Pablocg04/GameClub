"""Empaqueta builds release y comprueba los motores incluidos; no incluye ROMs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('platform', choices=('windows', 'android'))
    parser.add_argument('--archive', action='store_true', help='Prepara también el ZIP Windows para distribuirlo')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = re.search(r'^version:\s*([^+\s]+)', (root/'client/pubspec.yaml').read_text(encoding='utf-8'), re.M).group(1)
    assert (root/'dist').is_dir()
    registry = json.loads((root/'client/assets/native_console_cores.json').read_text(encoding='utf-8'))

    def verify_assets(read):
        for platform, entries in registry['platforms'].items():
            for core, entry in entries.items():
                data = read(f'assets/native-cores/{platform}/{core}.zip')
                assert len(data) == entry['size'] and hashlib.sha256(data).hexdigest() == entry['sha256']

    if args.platform == 'windows':
        source = root/'client/build/windows/x64/runner/Release'
        for filename in ('gameclub.exe', 'gameclub_native.exe', 'SDL3.dll', 'flutter_windows.dll'):
            assert (source/filename).is_file(), filename
        verify_assets(lambda name: (source/'data/flutter_assets'/name).read_bytes())
        target = root/'dist'/f'windows-{version}'
        shutil.copytree(source, target, dirs_exist_ok=True)
        for document in ('MAME_NATIVE.md', 'NATIVE_CONSOLES.md', 'THIRD_PARTY_NOTICES.md', 'THUMBNAILS.md', 'VERIFICATION.md'):
            shutil.copy2(root/document, target/document)
        print(target/'gameclub.exe', flush=True)
        if args.archive:
            destination = root/'dist'/f'GameClub-Windows-{version}.zip'
            with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for file in target.rglob('*'):
                    if file.is_file(): archive.write(file, 'GameClub/'+file.relative_to(target).as_posix())
            print(destination, flush=True)
    else:
        for variant, name in [('mobile','GameClub-Android.apk'), ('tv','GameClub-AndroidTV.apk')]:
            source = root/f'client/build/app/outputs/flutter-apk/app-{variant}-release.apk'
            with zipfile.ZipFile(source) as archive:
                verify_assets(lambda name: archive.read('assets/flutter_assets/'+name))
                for abi in ('armeabi-v7a', 'arm64-v8a', 'x86_64'):
                    assert f'lib/{abi}/libgameclub_native.so' in archive.namelist()
                assert not any(name.lower().endswith(('.nes', '.a26', '.sta')) for name in archive.namelist())
            target = root/'dist'/f'android-{variant}-{version}'
            target.mkdir(exist_ok=True)
            shutil.copy2(source, target/name)
            print(target/name, flush=True)


if __name__ == '__main__': main()
