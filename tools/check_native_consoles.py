"""Prueba local de NES/2600: usa copias temporales, nunca publica ROMs."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nes', type=Path, required=True)
    parser.add_argument('--atari', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--index', type=int, help='Repite solo una de las muestras 0..3')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    assert args.root.parent.is_dir() and args.nes.is_dir() and args.atari.is_dir()
    project = Path(__file__).resolve().parents[1]
    registry = json.loads((project / 'server/app/native_cores.json').read_text(encoding='utf-8'))['windows-x86_64']
    samples = [
        ('nes', 'nestopia', next(args.nes.glob('Super Mario Bros. (JU)*.nes'))),
        ('nes', 'nestopia', next(args.nes.glob('Super Mario Bros. 3 (U)*.nes'))),
        ('atari2600', 'stella', next(args.atari.glob('Pac-Man (1982)*Sears*~.bin'))),
        ('atari2600', 'stella', next(args.atari.glob('Pac-Man (1982)* (PAL).bin'))),
    ]
    for state in list(args.atari.glob('*.sta'))[:1]:
        print('STATE HEADER', state.name, repr(state.read_bytes()[:64]), flush=True)
    for system, core, source in samples:
        folder = args.root / 'roms' / system
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, folder / source.name)
    if args.prepare_only:
        return
    user = ctypes.windll.user32
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    for index, (system, core, source) in enumerate(samples):
        if args.index is not None and index != args.index: continue
        entry = registry[core]
        binary = args.root / entry['binary']
        with zipfile.ZipFile(project / 'data/native-cores/v1/windows-x86_64' / f'{core}.zip') as archive:
            raw = archive.read(entry['binary'])
        assert hashlib.sha256(raw).hexdigest() == entry['binary_sha256']
        binary.write_bytes(raw)
        saves = args.root / 'checks' / str(index)
        saves.mkdir(parents=True, exist_ok=True)
        report = saves / 'session.txt'
        for suffix in ('', '.bmp', '.after.bmp'):
            Path(str(report) + suffix).unlink(missing_ok=True)
        with (saves / 'host.log').open('wb') as log:
            process = subprocess.Popen([str(args.executable.resolve()), str(binary.resolve()),
                str((args.root / 'roms' / system / source.name).resolve()), str(saves.resolve()),
                str(report.resolve()), 'pad', system, 'verify'], stdout=log, stderr=log)
            def wait(predicate, timeout=45):
                end = time.monotonic() + timeout
                while time.monotonic() < end:
                    if predicate(): return
                    if process.poll() is not None:
                        raise RuntimeError(f'Motor cerrado: {process.returncode}; {report.read_text(errors="replace")}')
                    time.sleep(.2)
                raise TimeoutError(report.read_text(errors='replace'))
            def state(): return report.read_text(errors='replace') if report.exists() else ''
            try:
                wait(lambda: Path(str(report)+'.bmp').exists())
                handles = []
                def visit(handle, _):
                    pid = wintypes.DWORD()
                    user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
                    if pid.value == process.pid and user.IsWindowVisible(handle): handles.append(handle)
                    return True
                user.EnumWindows(callback_type(visit), 0)
                assert handles
                def key(code, duration=.2):
                    scan = user.MapVirtualKeyW(code, 0); flags = 1 | (scan << 16)
                    if code in (37, 38, 39, 40): flags |= 1 << 24
                    user.PostMessageW(handles[0], 0x100, code, flags); time.sleep(duration)
                    user.PostMessageW(handles[0], 0x101, code, flags | 0xc0000000); time.sleep(.2)
                Image.open(str(report)+'.bmp').save(saves / 'before.png')
                key(0x0d); time.sleep(1); key(0x0d); time.sleep(1); key(0x0d)
                key(0x27, .6); key(0x5a); key(0x27, .6)
                key(0x58); key(0x25, .6); key(0x28); key(0x5a)
                wait(lambda: Path(str(report)+'.after.bmp').exists())
                wait(lambda: 'inputs=10' in state())
                counters = dict(line.split('=', 1) for line in state().splitlines() if '=' in line)
                assert int(counters['consumed']) > 0 and int(counters['directions']) > 0, state()
                frame = Image.open(str(report)+'.after.bmp').convert('RGB')
                assert len(frame.getcolors(frame.width*frame.height) or []) > 2
                frame.save(saves / 'after.png')
                assert int(counters['audio_signals']) > 10, state()
                print(system, source.name, state(), flush=True)
                key(0x1b); wait(lambda: state().startswith('menu\n'))
                key(0x0d); wait(lambda: state().startswith('running\n'))
                key(0x1b); key(0x28); key(0x0d)
                assert process.wait(timeout=15) == 0
                assert state().startswith('closed\n'), state()
            finally:
                if process.poll() is None: process.terminate(); process.wait(timeout=10)
    print('Muestras seleccionadas: vídeo, audio, entradas, pausa, continuación y cierre correctos.', flush=True)


if __name__ == '__main__': main()
