"""Servidor de prueba aislado con una ROM propia ya cacheada y motores fijados."""
import argparse
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser()
parser.add_argument('root',type=Path)
parser.add_argument('--rom',type=Path,required=True)
parser.add_argument('--port',type=int,default=8692)
parser.add_argument('--system',choices=('mame','nes','atari2600'),default='mame')
args=parser.parse_args()
root=args.root.resolve();project=Path(__file__).resolve().parents[1]
assert root.parent.is_dir() and args.rom.is_file()
if args.system=='mame': assert args.rom.suffix.lower()=='.zip'
roms=root/'roms'/args.system;roms.mkdir(parents=True,exist_ok=True)
if args.rom.resolve() != (roms/args.rom.name).resolve():shutil.copy2(args.rom,roms/args.rom.name)
cache=root/'data'/'native-cores'/'v1'/'android-x86_64'
cache.mkdir(parents=True,exist_ok=True)
for source in (project/'data'/'native-cores'/'v1'/'android-x86_64').glob('*.zip') if args.system=='mame' else []:
    target=cache/source.name
    if not target.exists():shutil.copy2(source,target)
sys.path.insert(0,str(project/'server'))
from app.main import create_app
import uvicorn
uvicorn.run(create_app(root/'roms',root/'data',root/'media',token=''),host='0.0.0.0',port=args.port)
