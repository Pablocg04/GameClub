"""Audita lo que Git publicará: sin ROMs, cachés, builds ni credenciales."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    arguments = ['git', 'ls-files', '-z', '--cached'] if args.staged else ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard']
    files = sorted(set(subprocess.run(arguments, cwd=root, capture_output=True, check=True).stdout.decode('utf-8').rstrip('\0').split('\0')))
    registry = json.loads((root/'client/assets/native_console_cores.json').read_text(encoding='utf-8'))
    packages = {f'client/assets/native-cores/{platform}/{core}.zip': entry
        for platform, entries in registry['platforms'].items() for core, entry in entries.items()}
    blocked = {'.nes','.a26','.rom','.bin','.sta','.gb','.gbc','.gba','.nds','.dsi','.sfc','.smc','.chd','.iso','.7z','.rar','.exe','.dll','.so','.aar','.apk','.pem','.p12','.jks','.keystore'}
    secrets = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)')
    size = 0
    for relative in files:
        if not relative: continue
        path = root/relative
        assert relative.split('/')[0] not in {'roms','bios','media','data','dist','Pack Emuladores','.venv','.git'}, relative
        assert path.suffix.lower() not in blocked and '.sqlite3' not in path.name, relative
        assert not path.name.startswith('.env') or path.name == '.env.example', relative
        raw = path.read_bytes(); size += len(raw)
        assert len(raw) < 100*1024*1024, relative
        if path.suffix == '.zip':
            assert relative in packages, relative
            entry = packages[relative]
            assert hashlib.sha256(raw).hexdigest() == entry['sha256'], relative
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                assert archive.namelist() == [entry['binary']], relative
                assert hashlib.sha256(archive.read(entry['binary'])).hexdigest() == entry['binary_sha256'], relative
        elif path.suffix not in {'.gz', '.png', '.jpg', '.ico'}:
            assert not secrets.search(raw.decode('utf-8', 'replace')), 'Credencial detectada en '+relative
    print(f'{len(files)} archivos revisados, {size/1024/1024:.1f} MiB. Sin ROMs ni credenciales; ZIPs limitados a motores oficiales verificados.')


if __name__ == '__main__': main()
