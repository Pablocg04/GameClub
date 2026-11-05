"""Prepara las dependencias fijadas del port VPX/PinMAME sin instalar nada global."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile
from build_switch_pinball import ROOT, PORT, DEPS, LOCK, prepare_source, prepare_headers


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    subprocess.run([sys.executable, str(ROOT/'tools/prepare_switch_toolchain.py')], check=True)
    subprocess.run([sys.executable, str(ROOT/'tools/prepare_switch_toolchain.py'), '--lock',
                    str(PORT/'toolchain-extra-lock.json')], check=True)
    for name in LOCK:
        prepare_source(name)
        print('Fuentes verificadas: '+name, flush=True)
    lock = json.loads((PORT/'host-tools-lock.json').read_text())
    host = DEPS/'host-tools'
    host.mkdir(exist_ok=True)
    archive = host/lock['filename']
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != lock['sha256']:
        with urllib.request.urlopen(lock['url'], timeout=60) as response:
            raw = response.read(lock['size']+1)
        assert len(raw) == lock['size'] and hashlib.sha256(raw).hexdigest() == lock['sha256']
        archive.write_bytes(raw)
    with zipfile.ZipFile(archive) as zip:
        assert zip.testzip() is None
        for entry in zip.infolist():
            destination = host/entry.filename
            assert destination.resolve().is_relative_to(host.resolve())
            if not entry.is_dir():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(zip.read(entry))
    prepare_headers()
    # FlexDMD PNGs in the source checkout can be Git LFS pointers. Use the
    # hash-verified assets from the pinned official VPX distribution instead.
    registry = json.loads((ROOT/'client/platform-config/pinball_runtime.json').read_text())
    assets = ROOT/'client/native/vendor/pinball/assets/pinball'
    for name, entry in registry['assets'].items():
        if not name.startswith('plugins/flexdmd/assets/'):
            continue
        path = assets/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            subprocess.run([sys.executable, str(ROOT/'tools/prepare_android_pinball.py')], check=True)
            break
    print('SDK, fuentes, parches y Bison preparados en '+str(DEPS), flush=True)


if __name__ == '__main__':
    main()
