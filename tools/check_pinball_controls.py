"""Banco Windows: foco sin ayuda externa, mando SDL virtual, menú, reinicio y NVRAM."""
import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from PIL import Image, ImageGrab


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--trace-script', action='store_true')
    parser.add_argument('--nvram', type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    assert args.root.parent.is_dir()
    args.root.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='run-', dir=args.root))
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project/'server'))
    from app.pinball import inspect_package, table_script
    manifest = inspect_package(args.package)
    folder = root/'table'
    with zipfile.ZipFile(args.package) as archive:
        for item in manifest['files']:
            destination = folder/item['destination']
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item['member']) as source, destination.open('wb') as output:
                shutil.copyfileobj(source, output)
    if args.trace_script:
        primary=folder/manifest['table']
        with primary.open('rb') as source: script=table_script(source)
        script=script.replace('Sub AFM_KeyDown(ByVal Keycode)', 'Sub AFM_KeyDown(ByVal Keycode)\nDebug.Print "TRACE KEYDOWN " & Keycode & " LEFT=" & LeftFlipperKey & " RIGHT=" & RightFlipperKey & " START=" & StartGameKey & " TROUGH=" & bsTrough.Balls & " ANGLE=" & LeftFlipper.CurrentAngle & " SW22=" & Controller.Switch(22) & " SW24=" & Controller.Switch(24)')
        script=script.replace('Sub SolLFlipper(Enabled)', 'Sub SolLFlipper(Enabled)\nDebug.Print "TRACE SOLLEFT " & Enabled')
        primary.with_suffix('.vbs').write_text(script.replace('\r\n','\n').replace('\r','\n'), encoding='utf-8')
    if args.nvram:
        target=folder/'pinmame/nvram/afm_113b.nv';target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(args.nvram,target)
    preferences = root/'preferences'
    preferences.mkdir()
    (preferences/'VPinballX.ini').write_text('[Player]\nPlayfieldFullScreen=1\n[Plugin.PinMAME]\nEnable=1\n', encoding='utf-8')
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.GetAsyncKeyState.restype = ctypes.c_short
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def foreground():
        pid = wintypes.DWORD()
        handle = user.GetForegroundWindow()
        user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        return pid.value, handle
    def capture(name, pid):
        actual, handle = foreground()
        assert actual == pid, f'Foco incorrecto: esperado {pid}, actual {actual}'
        rect = wintypes.RECT()
        user.GetWindowRect(handle, ctypes.byref(rect))
        ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom)).save(root/name)
    messages = queue.Queue()
    history = []
    engine_pid = [0]
    with (root/'host.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(args.host.resolve()), '--pinball', str(args.runtime.resolve()),
            str((folder/manifest['table']).resolve()), str(preferences.resolve()), '--test-pad',
            *([] if args.nvram else ['--initialize']), '--warmup=15000'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', bufsize=1)
        def collect():
            for line in process.stdout:
                log.write(line); log.flush()
                history.append(line)
                if line.startswith('GAMECLUB_PINBALL_ENGINE '):
                    engine_pid[0] = int(line.split()[-1])
                if line.startswith('GAMECLUB_PINBALL_'):
                    messages.put(line.strip())
        thread = threading.Thread(target=collect, daemon=True)
        thread.start()
        def wait(state, timeout=90):
            end = time.monotonic()+timeout
            while time.monotonic() < end:
                try:
                    line = messages.get(timeout=.5)
                    if line == 'GAMECLUB_PINBALL_STATE '+state:
                        print(state, flush=True)
                        time.sleep(.3)
                        return
                except queue.Empty:
                    if process.poll() is not None:
                        raise RuntimeError(f'El host cerró con {process.returncode}: {root}')
            raise TimeoutError(f'No llega {state}: {root}')
        def command(text):
            process.stdin.write(text+'\n');process.stdin.flush();time.sleep(.13)
        def button(index, held): command(f'button {index} {int(held)}')
        def tap(index): button(index, True);button(index, False)
        def menu():
            command('button 4 1\nbutton 6 1')
            wait('menu')
            command('button 4 0\nbutton 6 0')
        def released():
            time.sleep(.2)
            assert not user.GetAsyncKeyState(0xa0)&0x8000, 'Flipper izquierdo retenido'
            assert not user.GetAsyncKeyState(0xa1)&0x8000, 'Flipper derecho retenido'
        try:
            if not args.nvram: wait('first-boot-complete')
            wait('menu')
            capture('controls.png', process.pid)
            nvram = folder/'pinmame/nvram/afm_113b.nv'
            assert nvram.is_file(), 'La inicialización no guardó el NVRAM'
            tap(0)
            wait('running')
            assert foreground()[0] == engine_pid[0], 'El host no activó VPX por sí mismo'
            for _ in range(4): tap(4)
            tap(6);time.sleep(12)
            button(0, True);time.sleep(1);button(0, False);time.sleep(2)
            capture('before-flippers.png', engine_pid[0])
            button(9, True);button(10, True)
            capture('flippers.png', engine_pid[0])
            assert user.GetAsyncKeyState(0xa0)&0x8000 and user.GetAsyncKeyState(0xa1)&0x8000
            before=Image.open(root/'before-flippers.png').convert('RGB')
            after=Image.open(root/'flippers.png').convert('RGB')
            for left,right in ((.39,.47),(.49,.57)):
                bounds=(int(before.width*left),int(before.height*.72),int(before.width*right),int(before.height*.83))
                def grey(pixel):return min(pixel)>110 and max(pixel)-min(pixel)<45
                a=before.crop(bounds);b=after.crop(bounds)
                pixels_a=getattr(a,'get_flattened_data',a.getdata)()
                pixels_b=getattr(b,'get_flattened_data',b.getdata)()
                changed=sum(grey(a)!=grey(b) for a,b in zip(pixels_a,pixels_b))
                assert changed>400, f'El flipper no se movió realmente ({changed} píxeles): {root}'
            menu();released();capture('paused.png', process.pid)
            button(9, False);button(10, False)
            tap(1)
            wait('running')
            button(9, True);button(10, True)
            command('disconnect');released()
            # Esc debe abrir el mismo menú, sin cerrar la mesa directamente.
            assert foreground()[0] == engine_pid[0]
            user.keybd_event(0x1b,1,0,0);time.sleep(.12);user.keybd_event(0x1b,1,2,0)
            wait('menu')
            _, handle = foreground()
            def key(vk):
                scan=user.MapVirtualKeyW(vk,0)
                flags=1|(scan<<16)|(0x01000000 if vk in (0x25,0x26,0x27,0x28) else 0)
                user.PostMessageW(handle,0x100,vk,flags);time.sleep(.12)
                user.PostMessageW(handle,0x101,vk,flags|0xc0000000);time.sleep(.12)
            key(0x28);key(0x0d)
            wait('restarting')
            wait('running')
            time.sleep(2)
            capture('reopened.png', engine_pid[0])
            assert nvram.is_file() and nvram.stat().st_size>0
            user.keybd_event(0x1b,1,0,0);time.sleep(.12);user.keybd_event(0x1b,1,2,0)
            wait('menu')
            _, handle = foreground()
            key(0x28);key(0x28);key(0x0d)
            assert process.wait(timeout=20)==0, 'El host no cerró normalmente'
            thread.join(timeout=5)
            native_log=(preferences/'vpinball.log').read_text(encoding='utf-8')
            assert 'Unpausing Game' in native_log
            assert native_log.count('Startup done')==(2 if args.nvram else 3)
            assert not any('ERROR' in line for line in native_log.splitlines()), native_log
            print('FOCO, PRIMER ARRANQUE, MANDO, FLIPPERS, MENÚ, LIBERACIÓN, REINICIO Y NVRAM CORRECTOS', root, flush=True)
        finally:
            if process.poll() is None:
                def close(handle, _):
                    pid=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
                    if pid.value==engine_pid[0]:user.PostMessageW(handle,0x10,0,0)
                    return True
                user.EnumWindows(callback(close),0)
                try:process.wait(timeout=20)
                except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)


if __name__ == '__main__':main()
