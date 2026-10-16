"""Comprueba vídeo, audio y entradas de Bowling con el ZIP propio en Windows."""
import argparse
import io
import hashlib
import json
import subprocess
import time
import zipfile
from pathlib import Path
import httpx
from PIL import Image
import ctypes
from ctypes import wintypes

parser=argparse.ArgumentParser()
parser.add_argument('root',type=Path)
parser.add_argument('--core',default='mame2003_plus')
parser.add_argument('--executable',type=Path,required=True)
parser.add_argument('--binary',type=Path,help='Motor ya extraído; se comprueba su huella si está en el registro nativo')
parser.add_argument('--play',action='store_true')
args=parser.parse_args()
assert args.root.is_dir() and (args.root/'wcbowl.zip').is_file()
binary=args.binary or args.root/f'{args.core}_libretro.dll'
if args.binary:assert binary.is_file(), 'No existe el motor indicado'
with httpx.Client(timeout=240,follow_redirects=True) as client:
    if not binary.exists():
        response=client.get(f'https://buildbot.libretro.com/nightly/windows/x86_64/latest/{binary.name}.zip').raise_for_status()
        (args.root/f'{args.core}.zip').write_bytes(response.content)
        binary.write_bytes(zipfile.ZipFile(io.BytesIO(response.content)).read(binary.name))
metadata=json.loads((Path(__file__).resolve().parents[1]/'server/app/native_cores.json').read_text(encoding='utf-8'))['windows-x86_64'].get(args.core)
if metadata:
    with binary.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    assert digest==metadata['binary_sha256'], 'El motor no coincide con la versión distribuida; usa --binary con el binario fijado'
saves=args.root/args.core;saves.mkdir(exist_ok=True)
report=saves/'session.txt';report.unlink(missing_ok=True)
Path(str(report)+'.bmp').unlink(missing_ok=True)
Path(str(report)+'.after.bmp').unlink(missing_ok=True)
with (saves/'host.log').open('wb') as log:
    process=subprocess.Popen([str(args.executable.resolve()),str(binary.resolve()),str((args.root/'wcbowl.zip').resolve()),str(saves.resolve()),str(report.resolve()),'pad','arcade','verify'],stdout=log,stderr=log)
    try:
        end=time.monotonic()+45
        while time.monotonic()<end and process.poll() is None:
            if Path(str(report)+'.bmp').exists():
                time.sleep(.3)
                Image.open(str(report)+'.bmp').save(saves/'frame.png')
                print('VIDEO',report,flush=True);break
            time.sleep(.5)
        print('Estado',process.poll(),report.read_text(errors='replace') if report.exists() else '',flush=True)
        if args.play and process.poll() is None:
            user=ctypes.windll.user32
            user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
            handles=[]
            callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
            def visit(handle,_):
                pid=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
                if pid.value==process.pid and user.IsWindowVisible(handle):handles.append(handle)
                return True
            user.EnumWindows(callback(visit),0)
            def key(code,duration=.2):
                scan=user.MapVirtualKeyW(code,0);flags=1|(scan<<16)
                if code in (37,38,39,40):flags|=1<<24
                user.PostMessageW(handles[0],0x100,code,flags);time.sleep(duration)
                user.PostMessageW(handles[0],0x101,code,flags|0xc0000000);time.sleep(.2)
            key(0x31);time.sleep(2)
            for _ in range(4):key(0x35)
            key(0x31);time.sleep(2)
            key(0x5a);key(0x27);key(0x28,.5);key(0x26,.5);key(0x5a)
            time.sleep(4)
            image=Path(str(report)+'.after.bmp')
            if image.exists():Image.open(image).save(saves/'after.png')
            time.sleep(6)
            assert image.exists(), 'Falta la captura posterior a las entradas'
            Image.open(image).save(saves/'score.png')
            state=report.read_text(errors='replace')
            print('PLAY',state,flush=True)
            counters=dict(line.split('=',1) for line in state.splitlines() if '=' in line)
            assert state.startswith('running\n'), state
            assert int(counters['inputs'])>=11 and int(counters['directions'])>0, state
            assert int(counters['audio_signals'])>0, state
            key(0x1b);key(0x28);key(0x0d)
            assert process.wait(timeout=15)==0
            assert report.read_text(errors='replace').startswith('closed\n')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=10)
