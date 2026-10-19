"""Extrae el motor fijado y comprueba su mesa de ejemplo en un directorio local."""
import argparse
from pathlib import Path
import subprocess
import sys
import zipfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--play', action='store_true')
    args = parser.parse_args()
    assert args.root.parent.is_dir()
    args.root.mkdir(exist_ok=True)
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project/'server'))
    from app.pinball import inspect_package, table_script
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    runtime = args.root/'runtime'
    runtime.mkdir(exist_ok=True)
    if not (runtime/'VPinballX_BGFX64.exe').exists():
        with zipfile.ZipFile(project/'data/pinball-runtime/v1/windows-x86_64/vpx.zip') as archive:
            assert all((runtime/item.filename).resolve().is_relative_to(runtime.resolve()) for item in archive.infolist())
            archive.extractall(runtime)
    table = runtime/'assets/exampleTable.vpx'
    with table.open('rb') as source: print('SCRIPT', table_script(source)[:3000], flush=True)
    print('AUDITORÍA', inspect_package(table), flush=True)
    print((runtime/'plugins/pinmame/plugin.cfg').read_text(encoding='utf-8'), flush=True)
    try:
        result = subprocess.run([str((runtime/'VPinballX_BGFX64.exe').resolve()), '-v'], cwd=runtime,
            capture_output=True, timeout=15)
        print('VERSIÓN', result.returncode, result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace'), flush=True)
    except subprocess.TimeoutExpired:
        print('La consulta de versión abre una ventana; el proceso de prueba se ha cerrado.', flush=True)
    if args.play:
        preferences = args.root/'preferences'; preferences.mkdir(exist_ok=True)
        ini = preferences/'VPinballX.ini'
        ini.write_text('[Player]\nPlayfieldFullScreen=1\nMaxFramerate=60\n[Plugin.PinMAME]\nEnable=1\n[Plugin.ScoreView]\nEnable=1\n[ScoreView]\nScoreViewOutput=2\nScoreViewWidth=320\nScoreViewHeight=120\nScoreViewWndX=16\nScoreViewWndY=16\n', encoding='utf-8')
        with (args.root/'player.log').open('wb') as output:
            process = subprocess.Popen([str((runtime/'VPinballX_BGFX64.exe').resolve()), '-Ini', str(ini.resolve()),
                '-PrefPath', str(preferences.resolve()), '-Play', str(table.resolve())], cwd=runtime,
                stdout=output, stderr=output)
            try:
                time.sleep(12)
                print('PLAYER', process.poll(), flush=True)
                (args.root/'player.png').unlink(missing_ok=True)
                if process.poll() is None:
                    import ctypes
                    from ctypes import wintypes
                    user = ctypes.windll.user32
                    handles = []
                    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                    def visit(handle, _):
                        pid = wintypes.DWORD(); user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
                        if pid.value == process.pid and user.IsWindowVisible(handle): handles.append(handle)
                        return True
                    user.EnumWindows(callback(visit), 0)
                    if handles:
                        user.SetForegroundWindow(handles[0]); time.sleep(.3)
                        if user.GetForegroundWindow() == handles[0]:
                            rect = wintypes.RECT(); user.GetWindowRect(handles[0], ctypes.byref(rect))
                            from PIL import ImageGrab
                            ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom)).save(args.root/'player.png')
            finally:
                if process.poll() is None: process.terminate(); process.wait(timeout=10)


if __name__ == '__main__': main()
