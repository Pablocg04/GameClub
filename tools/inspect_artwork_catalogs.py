"""Inspecciona los catálogos públicos, sin descargar juegos ni usar cuentas."""
import argparse
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    assert args.directory.parent.is_dir()
    args.directory.mkdir(exist_ok=True)
    sources = {
        'launchbox': 'https://gamesdb.launchbox-app.com/Metadata.zip',
        'wii': 'https://www.gametdb.com/wiitdb.zip',
        'ds': 'https://www.gametdb.com/dstdb.zip',
        '3ds': 'https://www.gametdb.com/3dstdb.zip',
        'wiiu': 'https://www.gametdb.com/wiiutdb.zip',
        'switch': 'https://www.gametdb.com/switchtdb.zip',
    }
    with httpx.Client(follow_redirects=True, timeout=240) as client:
        for name, url in sources.items():
            target = args.directory / (name+'.zip')
            if not target.exists():
                with client.stream('GET', url) as response:
                    response.raise_for_status()
                    with target.with_suffix('.part').open('wb') as output:
                        for chunk in response.iter_bytes(1024*1024): output.write(chunk)
                target.with_suffix('.part').replace(target)
            with zipfile.ZipFile(target) as archive:
                print(name, [(item.filename, item.file_size) for item in archive.infolist()], flush=True)
                xml = next(item for item in archive.infolist() if item.filename.lower().endswith('.xml') and ('metadata' in item.filename.lower() or name != 'launchbox'))
                seen = set()
                with archive.open(xml) as stream:
                    depth = 0; root = None
                    for event, element in ET.iterparse(stream, events=('start', 'end')):
                        if event == 'start':
                            depth += 1
                            if root is None: root = element
                            continue
                        if element.tag in {'Game', 'GameImage', 'GameAlternateName', 'game'} and element.tag not in seen:
                            print(ET.tostring(element, encoding='unicode')[:7000], flush=True)
                            seen.add(element.tag)
                            if element.tag == 'game' or len(seen) == 3: break
                        if depth == 2: root.clear()
                        depth -= 1


if __name__ == '__main__': main()
