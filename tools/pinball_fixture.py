"""Servidor local de mesas; enlaza el SDK fijado y no publica nada en la Pi."""
import argparse
import os
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser()
parser.add_argument('root',type=Path)
parser.add_argument('--package',type=Path,required=True)
parser.add_argument('--port',type=int,default=8697)
args=parser.parse_args()
project=Path(__file__).resolve().parents[1]
assert args.root.parent.is_dir() and args.package.is_file()
folder=args.root/'roms/vpinball'; folder.mkdir(parents=True,exist_ok=True)
target=folder/args.package.name
if target.resolve()!=args.package.resolve():shutil.copy2(args.package,target)
sdk=project/'data/pinball-runtime/v1/windows-x86_64/vpx.zip'
cache=args.root/'data/pinball-runtime/v1/windows-x86_64/vpx.zip'
cache.parent.mkdir(parents=True,exist_ok=True)
if not cache.exists():
    try:os.link(sdk,cache)
    except OSError:shutil.copy2(sdk,cache)
sys.path.insert(0,str(project/'server'))
from app.main import create_app
import uvicorn
uvicorn.run(create_app(args.root/'roms',args.root/'data',args.root/'media',token=''),host='127.0.0.1',port=args.port)
