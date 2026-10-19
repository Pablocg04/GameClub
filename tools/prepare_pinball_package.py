"""Empaqueta y valida una mesa local. No sube archivos a ningún servidor."""
import argparse
from pathlib import Path
import sys
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source, output = args.directory.resolve(), args.output.resolve()
    assert source.is_dir() and output.parent.is_dir()
    assert not output.is_relative_to(source), 'Guarda el paquete fuera de la carpeta que vas a comprimir'
    assert not output.exists(), 'Ya existe el paquete de destino'
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'server'))
    from app.pinball import inspect_package
    temporary = output.with_suffix('.part')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for file in source.rglob('*'):
                if file.is_symlink(): raise ValueError('No se empaquetan enlaces')
                if file.is_file(): archive.write(file, file.relative_to(source).as_posix())
        info = inspect_package(temporary, output.name)
        temporary.replace(output)
        print(output, info, flush=True)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__': main()
