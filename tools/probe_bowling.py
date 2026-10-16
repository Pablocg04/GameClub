"""Audita una copia del ZIP propio de Bowling contra el catálogo MAME 0.139 fijado."""
import argparse
from pathlib import Path
import sys
import zipfile
import httpx
import json

parser=argparse.ArgumentParser()
parser.add_argument('root',type=Path)
args=parser.parse_args()
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
assert args.root.parent.is_dir()
args.root.mkdir(exist_ok=True)
project=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(project/'server'))
from app.arcade import ArcadeCatalog
with httpx.Client(timeout=180,follow_redirects=True) as client:
    rom=args.root/'wcbowl.zip'
    if not rom.exists():
        game=next(game for game in client.get('http://192.168.0.47:8001/api/games').raise_for_status().json() if game['filename']=='wcbowl.zip')
        rom.write_bytes(client.get(f"http://192.168.0.47:8001/api/games/{game['id']}/download").raise_for_status().content)
    xml=args.root/'mame2010.xml'
    if not xml.exists():xml.write_bytes(client.get('https://raw.githubusercontent.com/libretro/mame2010-libretro/dff8aadd1c3f38215af3955746d6e19abe0ddcea/metadata/mame2010.xml').raise_for_status().content)
with zipfile.ZipFile(rom) as archive:
    inventory={(entry.CRC,entry.file_size) for entry in archive.infolist() if not entry.is_dir()}
    for entry in archive.infolist():print(entry.filename,entry.file_size,f'{entry.CRC:08x}')
catalog=ArcadeCatalog.parse(xml.read_bytes())
profile=project/'server'/'app'/'native_bowling.json'
assert all(not chip['crc'] or (int(chip['crc'],16),chip['size']) in inventory for chip in catalog['wcbowl']['roms']), 'El ZIP no coincide con el perfil completo de Bowling'
profile.write_text(json.dumps({'source':'MAME 0.139 dff8aadd1c3f38215af3955746d6e19abe0ddcea','games':{'wcbowl':catalog['wcbowl']}},indent=2)+'\n',encoding='utf-8')
for code,info in catalog.items():
    if not code.startswith('wcbowl'):continue
    missing=[rom for rom in info['roms'] if rom['crc'] and (int(rom['crc'],16),rom['size']) not in inventory]
    print(code,info['title'],'MATCH' if not missing else f'faltan {len(missing)}',missing)
