"""Prepara VPX oficial fijado, sin descargar mesas comerciales ni ROMs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import httpx

TAG = 'v10.8.1-5436-af26b2d93'
NAME = 'VPinballX_BGFX-10.8.1-5436-af26b2d93-windows-mingw-x64-Release.zip'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gh', default='gh', help='Ruta del ejecutable GitHub CLI')
    args = parser.parse_args()
    import subprocess
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    root = Path(__file__).resolve().parents[1]
    release = json.loads(subprocess.run([args.gh, 'api', f'repos/vpinball/vpinball/releases/tags/{TAG}'],
        capture_output=True, check=True, encoding='utf-8').stdout)
    asset = next(item for item in release['assets'] if item['name'] == NAME)
    folder = root/'data/pinball-runtime/v1'; folder.mkdir(parents=True, exist_ok=True)
    platform = folder/'windows-x86_64'; platform.mkdir(exist_ok=True)
    archive = platform/'vpx.zip'
    if not archive.exists() and (folder/'windows-x86_64.zip').exists():
        (folder/'windows-x86_64.zip').replace(archive)
    expected = asset['digest'].removeprefix('sha256:')
    def valid():
        if not archive.exists() or archive.stat().st_size != asset['size']: return False
        with archive.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest() == expected
    if not valid():
        temporary = archive.with_suffix('.part')
        with httpx.Client(timeout=240, follow_redirects=True) as client, client.stream('GET', asset['browser_download_url']) as response:
            response.raise_for_status()
            with temporary.open('wb') as output:
                for chunk in response.iter_bytes(1024*1024): output.write(chunk)
        temporary.replace(archive)
        assert valid(), 'El motor no coincide con su huella oficial'
    with zipfile.ZipFile(archive) as zipped:
        print('VPX', TAG, archive.stat().st_size, flush=True)
        files = {item.filename: {'size': item.file_size, 'sha256': hashlib.sha256(zipped.read(item)).hexdigest()}
                 for item in zipped.infolist() if not item.is_dir()}
    metadata = {'version': TAG, 'platforms': {'windows-x86_64': {
        'source': asset['browser_download_url'], 'size': asset['size'], 'sha256': expected,
        'binary': 'VPinballX_BGFX64.exe', 'files': files}}}
    (root/'server/app/pinball_runtime.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__': main()
