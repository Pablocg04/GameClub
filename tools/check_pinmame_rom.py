"""Consulta el PinMAME fijado sobre una ROM propia, sin ejecutar la máquina."""
import argparse
import ctypes
import os
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--game', required=True)
    args = parser.parse_args()
    assert args.root.parent.is_dir() and args.rom.is_file()
    roms = args.root/'roms'; roms.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.rom, roms/args.rom.name)
    class Game(ctypes.Structure):
        _fields_ = [('name', ctypes.c_char_p), ('parent', ctypes.c_char_p), ('description', ctypes.c_char_p),
                    ('year', ctypes.c_char_p), ('manufacturer', ctypes.c_char_p), ('flags', ctypes.c_uint32), ('found', ctypes.c_int32)]
    with os.add_dll_directory(str(args.runtime.resolve())):
        core = ctypes.CDLL(str((args.runtime/'pinmame64.dll').resolve()))
        config = ctypes.create_string_buffer(4096)
        ctypes.c_int.from_buffer(config, 4).value = 48000
        path = (str(args.root.resolve())+os.sep).encode('utf-8')
        assert len(path) < 512, 'La ruta supera el búfer de configuración de PinMAME'
        ctypes.memmove(ctypes.addressof(config)+8, path, len(path))
        core.PinmameSetConfig.argtypes = [ctypes.c_void_p]
        core.PinmameSetConfig(config)
        callback_type = ctypes.CFUNCTYPE(None, ctypes.POINTER(Game), ctypes.c_void_p)
        def show(pointer, _):
            game = pointer.contents
            print('GAME', game.name, 'PARENT', game.parent, 'FOUND', game.found, 'TITLE', game.description, flush=True)
        core.PinmameGetGame.argtypes = [ctypes.c_char_p, callback_type, ctypes.c_void_p]
        print('STATUS', core.PinmameGetGame(args.game.encode(), callback_type(show), None), flush=True)


if __name__ == '__main__': main()
