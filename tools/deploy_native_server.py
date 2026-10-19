"""Publica servidor y caché nativa en la instalación existente de GameClub."""
import argparse
import getpass
from pathlib import Path
import posixpath
import sys
import time
import shlex
import paramiko


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--password-stdin", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--server-only", action="store_true", help="Actualiza código y metadatos, sin transferir motores ni ROMs")
    parser.add_argument("--artwork-cache", action="store_true", help="Precarga índices públicos de carátulas, sin imágenes ni ROMs")
    parser.add_argument("--pinball-cache", action="store_true", help="Precarga el motor oficial VPX fijado, sin mesas ni ROMs")
    parser.add_argument("--check-artwork", action="store_true", help="Comprueba las fuentes públicas dentro del contenedor")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    root = Path(__file__).resolve().parents[1]
    remote = "/home/pablo/proyectos/GameClub"
    password = sys.stdin.readline().strip() if args.password_stdin else getpass.getpass("SSH: ")
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    known = Path.home() / "AppData/Local/Temp/opencode/gameclub_known_hosts"
    if known.exists(): ssh.load_host_keys(str(known))
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("192.168.0.47", username="pablo", password=password, look_for_keys=False, allow_agent=False, timeout=20)
    try:
        with ssh.open_sftp() as sftp:
            sftp.stat(remote)
            def mkdir(path):
                try: sftp.stat(path)
                except FileNotFoundError: mkdir(posixpath.dirname(path)); sftp.mkdir(path)
            if args.check_artwork:
                checker = posixpath.join(remote, '.artwork-preload', 'check_artwork_sources.py')
                mkdir(posixpath.dirname(checker))
                sftp.put(str(root/'tools/check_artwork_sources.py'), checker)
            files = list((root / "server/app").glob("*.py")) + list((root / "server/app").glob("*.json")) + list((root / "server/app").glob("*.gz"))
            files.append(root/'server/requirements.txt')
            if not args.server_only:
                files += sorted((root / "data/native-cores/v1").glob("*/*.zip"))
            if args.pinball_cache:
                runtime = root/'data/pinball-runtime/v1/windows-x86_64/vpx.zip'
                if not runtime.is_file(): raise FileNotFoundError('Prepara primero el motor con tools/fetch_pinball_runtime.py')
                files.append(runtime)
            for file in files:
                target = posixpath.join(remote, file.relative_to(root).as_posix())
                if file.suffix == ".zip":
                    try:
                        if sftp.stat(target).st_size == file.stat().st_size:
                            continue
                    except FileNotFoundError: pass
                mkdir(posixpath.dirname(target))
                print("Publicando", file.relative_to(root), flush=True)
                sftp.put(str(file), target + ".upload")
                sftp.posix_rename(target + ".upload", target)
            if args.artwork_cache:
                staged = []
                for file in sorted((root / 'data/artwork').glob('*.sqlite3')):
                    target = posixpath.join(remote, '.artwork-preload', file.name)
                    mkdir(posixpath.dirname(target))
                    print('Publicando índice de carátulas', file.name, flush=True)
                    sftp.put(str(file), target + '.upload')
                    sftp.posix_rename(target + '.upload', target)
                    staged.append((target, file.name))
        if args.artwork_cache:
            prepare = "from pathlib import Path;Path('/library/data/artwork').mkdir(parents=True,exist_ok=True)"
            commands = [f'docker exec gameclub python -c {shlex.quote(prepare)}']
            for source, name in staged:
                commands.append(f'docker cp {shlex.quote(source)} gameclub:/library/data/artwork/{name}.upload')
                publish = f"from pathlib import Path;Path('/library/data/artwork/{name}.upload').replace('/library/data/artwork/{name}')"
                commands.append(f'docker exec gameclub python -c {shlex.quote(publish)}')
            _, output, error = ssh.exec_command(' && '.join(commands), timeout=180)
            if output.channel.recv_exit_status() != 0:
                raise RuntimeError(error.read().decode('utf-8', 'replace'))
        if args.build:
            command = f"cd {shlex.quote(remote)} && docker compose up -d --build gameclub"
            _, output, error = ssh.exec_command(command, timeout=900)
            channel = output.channel
            while not channel.exit_status_ready() or channel.recv_ready() or channel.recv_stderr_ready():
                if channel.recv_ready(): print(channel.recv(65536).decode("utf-8", "replace"), end="", flush=True)
                if channel.recv_stderr_ready(): print(channel.recv_stderr(65536).decode("utf-8", "replace"), end="", flush=True)
                time.sleep(.05)
            if channel.recv_exit_status() != 0: raise RuntimeError("Fallo de Docker GameClub")
        if args.check_artwork:
            command = (f'docker cp {shlex.quote(checker)} gameclub:/tmp/check_artwork_sources.py && '
                       'docker exec -e PYTHONPATH=/app gameclub python /tmp/check_artwork_sources.py --data /library/data')
            _, output, error = ssh.exec_command(command, timeout=600)
            for line in output: print(line, end='', flush=True)
            if output.channel.recv_exit_status() != 0:
                raise RuntimeError(error.read().decode('utf-8', 'replace'))
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
