"""Crea programas de prueba propios y un servidor temporal para la integración.

No añade ROMs a la Raspberry ni modifica la biblioteca real.
"""
import argparse
import os
import struct
import subprocess
import sys
from pathlib import Path


def crc16(data):
    crc = 0xffff
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xa001 if crc & 1 else 0)
    return crc


def gb_rom(color=False):
    rom = bytearray(32768)
    rom[0x100:0x104] = bytes.fromhex("00 C3 50 01")
    rom[0x104:0x134] = bytes.fromhex("CEED6666CC0D000B03730083000C000D0008111F8889000EDCCC6EE6DDDDD999BBBB67636E0EECCCDDDC999FBBB9333E")
    rom[0x134:0x144] = b"GAMECLUB TEST   "
    if color:
        rom[0x143] = 0x80
    rom[0x147:0x14a] = bytes([3, 0, 2])  # MBC1, 32 KiB ROM, SRAM con batería.
    code = bytearray()
    labels, jumps = {}, []
    def emit(hex):
        code.extend(bytes.fromhex(hex))
    def label(name):
        labels[name] = len(code)
    def jr(op, target):
        jumps.append((len(code) + 1, target))
        code.extend([op, 0])
    emit("F3 3E 0A EA 00 00 FA 00 A0 3C EA 00 A0 AF E0 40")
    emit("21 00 80 06 08")
    label("tile")
    emit("3E FF 22 AF 22 05")
    jr(0x20, "tile")
    emit("21 00 98 01 00 04 16 00")
    label("map")
    emit("72 23 0B 78 B1")
    jr(0x20, "map")
    emit("3E E4 E0 47 3E 91 E0 40")
    label("poll")
    emit("3E 10 E0 00 F0 00 E6 01")
    jr(0x20, "released")
    emit("3E E0 16 03" if color else "3E 1B")
    jr(0x18, "palette")
    label("released")
    emit("3E 1F 16 00" if color else "3E E4")
    label("palette")
    emit("5F 3E 82 E0 68 7B E0 69 7A E0 69" if color else "E0 47")
    jr(0x18, "poll")
    for offset, target in jumps:
        code[offset] = (labels[target] - (offset + 1)) & 255
    rom[0x150:0x150 + len(code)] = code
    checksum = 0
    for byte in rom[0x134:0x14d]:
        checksum = (checksum - byte - 1) & 255
    rom[0x14d] = checksum
    struct.pack_into(">H", rom, 0x14e, (sum(rom) - rom[0x14e] - rom[0x14f]) & 0xffff)
    return bytes(rom)


def snes_rom():
    rom = bytearray(32768)
    code = bytearray()
    labels, jumps = {}, []
    def emit(hex):
        code.extend(bytes.fromhex(hex))
    def label(name):
        labels[name] = len(code)
    def branch(op, target):
        jumps.append((len(code) + 1, target))
        code.extend([op, 0])
    emit("78 18 FB C2 10 E2 20 A9 80 8D 00 21 9C 00 42 9C 2C 21 9C 21 21")
    emit("A9 1F 8D 22 21 A9 00 8D 22 21 A9 0F 8D 00 21")
    label("poll")
    emit("A9 01 8D 16 40 9C 16 40 A2 08 00")
    label("shift")
    emit("AD 16 40 CA")
    branch(0xd0, "shift")
    emit("AD 16 40 29 01")
    branch(0xf0, "released")
    emit("A9 E0 A2 03 00")
    branch(0x80, "palette")
    label("released")
    emit("A9 1F A2 00 00")
    label("palette")
    emit("9C 21 21 8D 22 21 8A 8D 22 21")
    branch(0x80, "poll")
    for offset, target in jumps:
        code[offset] = (labels[target] - (offset + 1)) & 255
    rom[:len(code)] = code
    rom[0x7fc0:0x7fd5] = b"GAMECLUB TEST PROGRAM"
    rom[0x7fd5:0x7fdc] = bytes([0x20, 0, 5, 0, 1, 0, 0])
    for offset in (0x7fea, 0x7fee, 0x7ffa, 0x7ffc, 0x7ffe):
        struct.pack_into('<H', rom, offset, 0x8000)
    checksum = (sum(rom) + 510) & 0xffff
    struct.pack_into('<HH', rom, 0x7fdc, checksum ^ 0xffff, checksum)
    return bytes(rom)


def compile_arm(source, directory, llvm, cpu):
    object = directory / f"{source.stem}.o"
    output = directory / f"{source.stem}.bin"
    subprocess.run([str(llvm / "clang.exe"), "--target=arm-none-eabi", f"-mcpu={cpu}",
                    "-c", str(source), "-o", str(object)], check=True)
    subprocess.run([str(llvm / "llvm-objcopy.exe"), "-O", "binary", "--only-section=.text", str(object), str(output)], check=True)
    return output.read_bytes()


def nds_rom(program, arm7):
    rom = bytearray(2048)
    rom[:12] = b"GAMECLUB NDS"
    rom[12:16] = b"GCTE"
    rom[16:18] = b"00"
    struct.pack_into("<4I", rom, 0x20, 0x200, 0x02000000, 0x02000000, len(program))
    struct.pack_into("<4I", rom, 0x30, 0x400, 0x03800000, 0x03800000, len(arm7))
    struct.pack_into("<I", rom, 0x80, len(rom))
    struct.pack_into("<I", rom, 0x84, 0x200)
    struct.pack_into("<H", rom, 0x15e, crc16(rom[:0x15e]))
    rom[0x200:0x200 + len(program)] = program
    rom[0x400:0x400+len(arm7)] = arm7
    return bytes(rom)


def gba_rom(program):
    rom = bytearray(1024)
    struct.pack_into("<I", rom, 0, 0xea00002e)  # Salta a 0xc0.
    rom[0xa0:0xac] = b"GAMECLUB GBA"
    rom[0xac:0xb0] = b"GCTA"
    rom[0xb0:0xb2] = b"00"
    rom[0xb2] = 0x96
    rom[0xbd] = (-(sum(rom[0xa0:0xbd]) + 0x19)) & 255
    rom[0xc0:0xc0 + len(program)] = program
    return bytes(rom)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8687)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    fixtures = Path(__file__).parent / "fixtures"
    programs = {
        "gb": gb_rom(),
        "gbc": gb_rom(color=True),
        "snes": snes_rom(),
        "nds": nds_rom(compile_arm(fixtures / "nds.s", args.root, args.llvm, "arm946e-s"),
                       compile_arm(fixtures / "nds_arm7.s", args.root, args.llvm, "arm7tdmi")),
        "gba": gba_rom(compile_arm(fixtures / "gba.s", args.root, args.llvm, "arm7tdmi")),
    }
    for system, data in programs.items():
        folder = args.root / "roms" / system
        folder.mkdir(parents=True, exist_ok=True)
        extension = "sfc" if system == "snes" else system
        (folder / f"gameclub-test.{extension}").write_bytes(data)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
    from app.main import create_app
    import uvicorn
    app = create_app(args.root / "roms", args.root / "data", args.root / "media", token="")
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
