"""Prepara bibliotecas y recursos VPX Android oficiales, fijados por SHA-256.

No instala el APK de VPX: sus componentes se incorporan al APK de GameClub.
SDL y libc++ son los del proyecto para conservar una única ABI compatible.
"""
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import httpx

TAG = 'v10.8.1-5436-af26b2d93'
NAME = 'VPinballX_BGFX-10.8.1-5436-af26b2d93-android-mobile-Release.apk'
SHA256 = '6fe3a346cbb8f20891e4549ded54faa7c8da3df314343132956276ec5132fcc9'
SIZE = 282314412
URL = f'https://github.com/vpinball/vpinball/releases/download/{TAG}/{NAME}'
LICENSE_URL = 'https://raw.githubusercontent.com/vpinball/vpinball/af26b2d9392b4c9ec3e3edff4bbd69562085a44c/docs/license.txt'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    root = Path(__file__).resolve().parents[1]
    cache = root/'data/pinball-runtime/android/v1'
    cache.mkdir(parents=True, exist_ok=True)
    apk = cache/NAME
    def valid():
        if not apk.is_file() or apk.stat().st_size != SIZE: return False
        with apk.open('rb') as source:
            return hashlib.file_digest(source, 'sha256').hexdigest() == SHA256
    if not valid():
        temporary = apk.with_suffix('.part')
        try:
            with httpx.stream('GET', URL, timeout=240, follow_redirects=True) as response, temporary.open('wb') as output:
                response.raise_for_status()
                count = 0
                for chunk in response.iter_bytes(1024*1024):
                    count += len(chunk)
                    if count > SIZE: raise ValueError('Tamaño de VPX distinto del fijado')
                    output.write(chunk)
            temporary.replace(apk)
            assert valid(), 'SHA-256 de VPX incorrecto'
        finally:
            temporary.unlink(missing_ok=True)
    vendor = root/'client/native/vendor/pinball'
    registry = {'version': TAG, 'source': URL, 'sha256': SHA256, 'size': SIZE,
                'android_api': 33, 'abi': 'arm64-v8a', 'libraries': {}, 'assets': {}}
    with zipfile.ZipFile(apk) as archive:
        for item in archive.infolist():
            name = item.filename
            if item.is_dir(): continue
            if name.startswith('lib/arm64-v8a/'):
                filename = Path(name).name
                if filename in {'libSDL3.so', 'libc++_shared.so', 'libandroidx.graphics.path.so', 'libopenxr_loader.so'}:
                    (vendor/'jniLibs/arm64-v8a'/filename).unlink(missing_ok=True)
                    continue
                destination = vendor/'jniLibs/arm64-v8a'/filename
                group, key = 'libraries', filename
            elif name.startswith(('assets/assets/', 'assets/scripts/', 'assets/plugins/')):
                relative = name.removeprefix('assets/')
                if Path(relative).suffix.lower() in {'.vpx', '.vpxz', '.directb2s', '.rom', '.nv', '.sta'}: continue
                destination = vendor/'assets/pinball'/relative
                group, key = 'assets', relative
            else: continue
            raw = archive.read(item)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            registry[group][key] = {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        print('Bibliotecas:', [(key, value['size']) for key, value in registry['libraries'].items()], flush=True)
        print('Recursos:', len(registry['assets']), 'archivos,', sum(value['size'] for value in registry['assets'].values()), 'bytes', flush=True)
    response = httpx.get(LICENSE_URL, timeout=60, follow_redirects=True)
    response.raise_for_status()
    notice = vendor/'assets/pinball/licenses/VisualPinball.txt'
    notice.parent.mkdir(parents=True, exist_ok=True)
    notice.write_bytes(response.content)
    registry['license_source'] = LICENSE_URL
    registry['assets']['licenses/VisualPinball.txt'] = {'size': len(response.content), 'sha256': hashlib.sha256(response.content).hexdigest()}
    target = root/'client/platform-config/pinball_runtime.json'
    target.write_text(json.dumps(registry, indent=2)+'\n', encoding='utf-8')
    (vendor/'assets/pinball-runtime.json').write_text(json.dumps(registry), encoding='utf-8')
    print(target, flush=True)


if __name__ == '__main__': main()
