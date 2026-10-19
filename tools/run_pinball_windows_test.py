"""Integración Windows con paquete propio; el teclado se dirige solo al proceso VPX de prueba."""
import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import time
import httpx
from PIL import ImageGrab


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--flutter',required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--package',type=Path,required=True)
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    assert args.root.parent.is_dir()
    args.root.mkdir(exist_ok=True)
    project=Path(__file__).resolve().parents[1]
    user=ctypes.windll.user32
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def windows(pid):
        found=[]
        def visit(handle,_):
            process=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(process))
            rect=wintypes.RECT();user.GetWindowRect(handle,ctypes.byref(rect))
            if process.value==pid and user.IsWindowVisible(handle) and rect.right-rect.left>600 and rect.bottom-rect.top>300:found.append(handle)
            return True
        user.EnumWindows(callback(visit),0)
        return found
    def key(handle,code,duration=.2):
        scan=user.MapVirtualKeyW(code,0)
        flags=1|(scan<<16)
        user.PostMessageW(handle,0x100,code,flags);time.sleep(duration)
        user.PostMessageW(handle,0x101,code,flags|0xc0000000);time.sleep(.2)
    def capture(handle,name):
        user.SetForegroundWindow(handle);time.sleep(.3)
        if user.GetForegroundWindow()!=handle:return
        rect=wintypes.RECT();user.GetWindowRect(handle,ctypes.byref(rect))
        ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom)).save(args.root/name)
    process=None
    pid=None
    with (args.root/'api.log').open('wb') as log:
        api=subprocess.Popen([sys.executable,str(project/'tools/pinball_fixture.py'),str(args.root),
            '--package',str(args.package),'--port','8697'],stdout=log,stderr=log)
        try:
            with httpx.Client(timeout=2) as client:
                end=time.monotonic()+30
                while time.monotonic()<end:
                    try:client.get('http://127.0.0.1:8697/health').raise_for_status();break
                    except httpx.HTTPError:time.sleep(.5)
                else:raise RuntimeError('El servidor de pinball no arrancó')
            process=subprocess.Popen([args.flutter,'drive','--driver=integration_test/tv_driver.dart',
                '--target=integration_test/pinball_test.dart','-d','windows','--no-dds'],cwd=project/'client',
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
            with (args.root/'driver.log').open('w',encoding='utf-8') as output:
                for line in process.stdout:
                    output.write(line);output.flush()
                    if any(marker in line for marker in ('PINBALL_','All tests','Expected:','Actual:','Error','Built ')):print(line,end='',flush=True)
                    if 'PINBALL_ENGINE_PID ' in line:
                        pid=int(line.split('PINBALL_ENGINE_PID ',1)[1].split()[0])
                        end=time.monotonic()+60;handles=[]
                        while time.monotonic()<end:
                            handles=windows(pid)
                            if handles:break
                            time.sleep(.5)
                        assert handles,'No hay ventana del reproductor VPX'
                        time.sleep(15)
                        handle=windows(pid)[0]
                        capture(handle,'before.png')
                        for _ in range(4):key(handle,0x35)
                        key(handle,0x31,.8);time.sleep(8)
                        key(handle,0x0d,1.2);time.sleep(3)
                        # Captura con ambos flippers pulsados, y suelta antes de salir.
                        assert user.GetForegroundWindow()==handle,'VPX perdió el foco antes de comprobar los flippers'
                        try:
                            for code in (0xa0,0xa1):user.keybd_event(code,user.MapVirtualKeyW(code,0),0,0)
                            time.sleep(.5);capture(handle,'after.png')
                        finally:
                            for code in (0xa0,0xa1):user.keybd_event(code,user.MapVirtualKeyW(code,0),2,0)
                        key(handle,0x1b)
            assert process.wait(timeout=30)==0,'Fallo de la integración: consulta driver.log'
        finally:
            if process is not None and process.poll() is None:
                if pid is not None:
                    for handle in windows(pid):user.PostMessageW(handle,0x10,0,0)
                process.terminate()
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            api.terminate();api.wait(timeout=15)


if __name__=='__main__':main()
