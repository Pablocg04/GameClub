"""Banco del host Windows: ROMs propias de la API, vídeo y teclado dirigido a su ventana."""
import argparse
import ctypes
from ctypes import wintypes
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile
import httpx
from PIL import Image


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--game',default='arkanoid.zip')
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    assert args.root.parent.is_dir() and args.executable.is_file()
    args.root.mkdir(exist_ok=True)
    with httpx.Client(base_url='http://192.168.0.47:8001',timeout=240) as api:
        games=api.get('/api/games').raise_for_status().json()
        game=next(game for game in games if game['system_id']=='mame' and game['filename']==args.game)
        plan=api.get(f"/api/games/{game['id']}/arcade/cores",params={'native':True,'identify':True}).raise_for_status().json()['candidates'][0]
        core=plan['core']
        metadata=api.get('/api/player/native').raise_for_status().json()['platforms']['windows-x86_64'][core]
        binary=args.root/metadata['binary']
        if not binary.exists():
            raw=api.get(f'/api/player/native/windows-x86_64/{core}').raise_for_status().content
            binary.write_bytes(zipfile.ZipFile(io.BytesIO(raw)).read(metadata['binary']))
        folder=args.root/args.game.replace('.zip','')
        folder.mkdir(exist_ok=True)
        # El MAME completo interpreta carpetas con nombre de máquina como software lists.
        roms=folder/'roms';roms.mkdir(exist_ok=True)
        for entry in plan['files']:
            dest=roms/entry['destination']
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():dest.write_bytes(api.get('/api/mame/download',params={'path':entry['path']}).raise_for_status().content)
    saves=folder/'saves';saves.mkdir(exist_ok=True)
    report=saves/'session.txt';report.unlink(missing_ok=True)
    capture=Path(str(report)+'.bmp');capture.unlink(missing_ok=True)
    args_core=[str(binary),str(roms/(plan['game_code']+'.zip')),str(saves),str(report),'pad',
               'cards' if plan['game_code'] in ('barline','cfever61','rcasino') else 'arcade','verify']
    log=(saves/'host.log').open('wb')
    process=subprocess.Popen([str(args.executable.resolve()),*args_core],cwd=args.executable.parent,stdout=log,stderr=log)
    user=ctypes.windll.user32
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def window():
        handles=[]
        def visit(handle,_):
            pid=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
            if pid.value==process.pid and user.IsWindowVisible(handle):handles.append(handle)
            return True
        user.EnumWindows(callback_type(visit),0)
        return handles[0] if handles else None
    def key(code):
        handle=window();assert handle,'No hay ventana SDL'
        scan=user.MapVirtualKeyW(code,0);flags=1|(scan<<16)
        if code in (37,38,39,40):flags|=1<<24
        user.PostMessageW(handle,0x100,code,flags);time.sleep(.15)
        user.PostMessageW(handle,0x101,code,flags|0xc0000000);time.sleep(.15)
    def state():return report.read_text(errors='replace') if report.exists() else ''
    def wait(predicate,timeout=120):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if predicate():return
            if process.poll() is not None:raise RuntimeError(f'Motor cerrado ({process.returncode}): {state()}')
            time.sleep(.2)
        raise TimeoutError(state())
    try:
        wait(lambda:capture.exists())
        frame=Image.open(capture).convert('RGB')
        center=frame.crop((frame.width//4,frame.height//4,frame.width*3//4,frame.height*3//4))
        assert len(center.getcolors(center.width*center.height) or [])>2
        frame.save(folder/'native.png')
        print(args.game,core,state(),flush=True)
        key(0x35);key(0x31);key(0x27)
        wait(lambda:'inputs=3' in state() or 'inputs=4' in state())
        key(0x1b);wait(lambda:state().startswith('menu\n'))
        key(0x28);key(0x26);key(0x0d)
        wait(lambda:state().startswith('running\n'))
        key(0x1b);key(0x28);key(0x0d)
        assert process.wait(timeout=15)==0
        assert state().startswith('closed\n')
        print('Windows nativo: vídeo, entradas, pausa, continuación y salida correctos.',flush=True)
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=15)
        log.close()


if __name__=='__main__':main()
