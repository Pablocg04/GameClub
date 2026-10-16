"""Banco aislado de GB/GBC/GBA/SNES/NDS con programas propios del proyecto."""
import argparse
from pathlib import Path
import subprocess
import sys
import time
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--flutter', required=True)
    parser.add_argument('--platform', choices=('windows', 'android'), required=True)
    parser.add_argument('--device', default='emulator-5554')
    parser.add_argument('--llvm', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8695)
    parser.add_argument('--systems', default='nds,gb,gba,gbc,snes')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    assert args.root.parent.is_dir()
    args.root.mkdir(exist_ok=True)
    project = Path(__file__).resolve().parents[1]
    with (args.root/'regression-server.log').open('wb') as log:
        server = subprocess.Popen([sys.executable, str(project/'tools/player_fixture.py'), str(args.root),
            '--llvm', str(args.llvm), '--port', str(args.port)], stdout=log, stderr=log)
        try:
            with httpx.Client(timeout=2) as client:
                end = time.monotonic()+30
                while time.monotonic() < end:
                    try:
                        client.get(f'http://127.0.0.1:{args.port}/health').raise_for_status(); break
                    except httpx.HTTPError:
                        if server.poll() is not None: raise RuntimeError('El servidor de pruebas no arrancó')
                        time.sleep(.5)
                else: raise TimeoutError('El servidor de pruebas no responde')
            base = f'http://{"127.0.0.1" if args.platform=="windows" else "10.0.2.2"}:{args.port}'
            command = [args.flutter, 'drive', '--driver=integration_test/tv_driver.dart',
                '--target=integration_test/player_test.dart', '--dart-define=PLAYER_TEST_SERVER='+base,
                '--dart-define=PLAYER_TEST_SYSTEMS='+args.systems,
                '-d', 'windows' if args.platform=='windows' else args.device, '--no-dds']
            if args.platform == 'android': command += ['--flavor', 'mobile']
            process = subprocess.Popen(command, cwd=project/'client', stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace')
            destination = args.root/f'player-{args.platform}.log'
            with destination.open('w', encoding='utf-8') as output:
                for line in process.stdout:
                    output.write(line); output.flush()
                    if any(marker in line for marker in ('Motor ', 'Pantalla táctil', 'NDS ', 'All tests', 'Expected:', 'Actual:', 'TestFailure', 'EXCEPTION', 'Error:', 'FAILED', 'Built ', 'Building Windows', 'Installing ')):
                        print(line, end='', flush=True)
            if process.wait() != 0: raise RuntimeError(f'Fallo del reproductor; registro completo: {destination}')
        finally:
            server.terminate(); server.wait(timeout=15)


if __name__ == '__main__': main()
