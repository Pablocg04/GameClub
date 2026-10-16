"""Copia de referencia del adaptador del core, sin modificar los binarios."""
import argparse
from pathlib import Path
import httpx
import zipfile
parser=argparse.ArgumentParser()
parser.add_argument('root',type=Path)
args=parser.parse_args()
assert args.root.is_dir()
with httpx.Client(timeout=60,follow_redirects=True) as client:
    for name in ('retromain.c','retromain.h'):
        response=client.get('https://raw.githubusercontent.com/libretro/mame2010-libretro/dff8aadd1c3f38215af3955746d6e19abe0ddcea/src/osd/retro/'+name)
        response.raise_for_status()
        (args.root/name).write_bytes(response.content)
project=Path(__file__).resolve().parents[1]
with zipfile.ZipFile(project/'data/native-cores/v1/android-x86_64/mame2010.zip') as archive:
    (args.root/'mame2010.so').write_bytes(archive.read('mame2010_libretro_android.so'))
