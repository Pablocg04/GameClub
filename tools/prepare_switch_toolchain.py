"""Prepara devkitA64/libnx portable en dist, con paquetes oficiales fijados por SHA-256."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--lock', type=Path, help='Manifiesto de paquetes adicionales fijados por SHA-256')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = (args.directory or root/'dist/switch-toolchain').resolve()
    destination.mkdir(parents=True, exist_ok=True)
    extraction = destination/'root'
    extraction.mkdir(exist_ok=True)
    packages = json.loads((args.lock or root/'switch-client/toolchain-lock.json').read_text())

    def fetch(package):
        target = destination/package['file']
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != package['sha256']:
            request = urllib.request.Request('https://pkg.devkitpro.org/packages/'+package['repo']+package['file'],
                headers={'User-Agent': 'pacman/6.1.0 (Windows x86_64) libalpm/14.0.0'})
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
            assert len(raw) == package['size'] and hashlib.sha256(raw).hexdigest() == package['sha256'], package['name']
            target.write_bytes(raw)
        return target

    links = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        for archive in executor.map(fetch, packages):
            print('Verificado: '+archive.name, flush=True)
            with tarfile.open(archive) as source:
                for member in source:
                    if member.name.startswith('.'):
                        continue
                    target = extraction/member.name
                    assert target.resolve().is_relative_to(extraction), member.name
                    if member.isfile():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        raw = source.extractfile(member).read()
                        if not target.is_file() or target.read_bytes() != raw:
                            target.write_bytes(raw)
                    elif member.islnk() or member.issym():
                        original = extraction/member.linkname if member.islnk() else target.parent/member.linkname
                        assert original.resolve().is_relative_to(extraction), member.linkname
                        links.append((original, target))
    for original, target in links:
        if original.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.read_bytes() != original.read_bytes():
                shutil.copyfile(original, target)
        else:
            raise RuntimeError('Enlace de paquete sin destino: '+str(original))
    print(extraction/'opt/devkitpro', flush=True)


if __name__ == '__main__':
    main()
