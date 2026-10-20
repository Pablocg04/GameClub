"""Paquetes VPX: validación, dependencias y rutas portables para el reproductor."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import tempfile
import zipfile
from functools import lru_cache

import olefile
from fastapi import HTTPException

OLE_MAGIC = bytes.fromhex('d0cf11e0a1b11ae1')
MAX_PACKAGE = 4 * 1024**3
MAX_UNPACKED = 8 * 1024**3
MAX_FILES = 10000
BLOCKED = {'.exe', '.dll', '.so', '.apk', '.bat', '.cmd', '.ps1', '.sh', '.lnk', '.url'}
PINBALL_ARTWORK_ID = 10001
MAME_PINBALL_ROOTS = ('pbaction', 'pinbo', 'speedbal', 'spbactn', 'gcpinbal', 'galspnbl',
                      'hotpinbl', 'timescan', 'pbchmp95', 'vspinbal')


def is_arcade_pinball(path):
    return PurePosixPath(path).stem.lower().startswith(MAME_PINBALL_ROOTS)


def safe_member(name):
    name = name.replace('\\', '/')
    parts = name.split('/')
    reserved = re.compile(r'^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', re.I)
    if (name.startswith('/') or any(part in {'', '.', '..'} or part.rstrip(' .') != part
        or any(c in part for c in ':<>"|?*') or any(ord(c) < 32 for c in part)
        or reserved.match(part) for part in parts)):
        raise HTTPException(422, f'Ruta inválida dentro del paquete: {name[:180]}')
    return PurePosixPath(name)


def table_script(stream):
    """Lee el CODE BIFF del contenedor OLE sin ejecutar el VBScript."""
    try:
        stream.seek(0)
        with olefile.OleFileIO(stream) as table:
            if not table.exists('GameStg/GameData'):
                raise ValueError('Falta GameData')
            with table.openstream('GameStg/GameData') as data:
                raw = data.read(32 * 1024 * 1024)
        offset = 0
        while offset + 8 <= len(raw):
            length = struct.unpack_from('<I', raw, offset)[0]
            tag = raw[offset+4:offset+8]
            if tag == b'CODE':
                size = struct.unpack_from('<I', raw, offset+8)[0]
                if size > 16 * 1024 * 1024 or offset+12+size > len(raw):
                    raise ValueError('Script truncado')
                return raw[offset+12:offset+12+size].decode('utf-8-sig', errors='replace')
            if length < 4 or offset+4+length > len(raw): break
            offset += 4+length
        return ''
    except (OSError, ValueError, struct.error):
        raise HTTPException(422, 'El archivo .vpx no contiene una mesa Visual Pinball válida') from None


def rom_references(script):
    lines = []
    for line in script.splitlines():
        if re.match(r'^\s*(?:\'|rem\s)', line, re.I): continue
        quoted = False
        for index, char in enumerate(line):
            if char == '"': quoted = not quoted
            if char == "'" and not quoted:
                line = line[:index]; break
        lines.append(line)
    text = '\n'.join(lines)
    names = re.findall(r'(?:\bcGameName|\bGameName|\.GameName)\s*=\s*"([a-zA-Z0-9_-]{1,100})"', text, re.I)
    needed = bool(names or re.search(r'VPinMAME\.Controller|\bLoadVPM\b|\bVPMInit\b', text, re.I))
    return list(dict.fromkeys(name.lower() for name in names)), needed


def inspect_package(path, filename=None):
    path = Path(path)
    filename = filename or path.name
    if path.stat().st_size > MAX_PACKAGE:
        raise HTTPException(413, 'Máximo 4 GiB por paquete de pinball')
    extension = Path(filename).suffix.lower()
    if extension == '.vpx':
        with path.open('rb') as table:
            if table.read(8) != OLE_MAGIC: raise HTTPException(422, 'El archivo no es una mesa .vpx')
            script = table_script(table)
        roms, required = rom_references(script)
        if required:
            raise HTTPException(422, 'Esta mesa necesita su ROM. Sube un ZIP con el .vpx y '+(', '.join(name+'.zip' for name in roms) or 'su ROM ZIP'))
        return {'table': Path(filename).name, 'files': [], 'roms': [], 'rom_candidates': [],
                'has_backglass': False, 'requires_rom': False, 'raw_table': True}
    if extension not in {'.zip', '.vpxz'}:
        raise HTTPException(422, 'Visual Pinball necesita un ZIP/VPXZ con una mesa, o un .vpx autosuficiente')
    try:
        with zipfile.ZipFile(path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if not members or len(members) > MAX_FILES or sum(item.file_size for item in members) > MAX_UNPACKED:
                raise HTTPException(422, 'El paquete está vacío o excede los límites de archivos/tamaño')
            names, seen = {}, set()
            for item in members:
                relative = safe_member(item.filename)
                if item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16):
                    raise HTTPException(422, 'El paquete no admite archivos cifrados ni enlaces')
                if relative.suffix.lower() in BLOCKED:
                    raise HTTPException(422, f'El paquete contiene un ejecutable o instalador: {relative.name}')
                if str(relative).casefold() in seen: raise HTTPException(422, 'Hay nombres duplicados en el paquete')
                seen.add(str(relative).casefold()); names[item.filename] = relative
            tables = [item for item in members if names[item.filename].suffix.lower() == '.vpx']
            if len(tables) != 1:
                raise HTTPException(422, 'Cada paquete debe contener exactamente una mesa .vpx')
            table = tables[0]
            table_name = names[table.filename]
            with archive.open(table) as source, tempfile.TemporaryFile() as temporary:
                if source.read(8) != OLE_MAGIC: raise HTTPException(422, 'La mesa .vpx no es válida')
                with archive.open(table) as full: shutil.copyfileobj(full, temporary)
                script = table_script(temporary)
            override = next((item for item in members if names[item.filename].with_suffix('') == table_name.with_suffix('')
                             and names[item.filename].suffix.lower() == '.vbs'), None)
            if override:
                if override.file_size > 16*1024*1024: raise HTTPException(422, 'El script de la mesa es demasiado grande')
                script = archive.read(override).decode('utf-8-sig', errors='replace')
            references, required = rom_references(script)
            files, roms, destinations = [], [], set()
            backglasses = [item for item in members if names[item.filename].suffix.lower() == '.directb2s']
            if len(backglasses) > 1: raise HTTPException(422, 'Incluye solo un panel .directb2s por mesa')
            for item in members:
                relative = names[item.filename]
                if relative.suffix.lower() == '.zip':
                    if item.file_size > 512*1024*1024: raise HTTPException(422, 'ROM ZIP demasiado grande')
                    try:
                        with zipfile.ZipFile(io.BytesIO(archive.read(item))) as rom:
                            chips = [chip for chip in rom.infolist() if not chip.is_dir()]
                            if not chips or len(chips) > 1000 or sum(chip.file_size for chip in chips) > 1024**3:
                                raise ValueError('ROM vacía o excesiva')
                            for chip in chips:
                                chip_path = safe_member(chip.filename)
                                if chip.flag_bits & 1 or chip_path.suffix.lower() in BLOCKED | {'.vpx', '.vpxz', '.zip'}:
                                    raise ValueError('No es una ROM')
                    except (zipfile.BadZipFile, ValueError):
                        raise HTTPException(422, f'La ROM {relative.name} no es un ZIP de chips válido') from None
                    destination = PurePosixPath('pinmame/roms')/relative.name.lower()
                    roms.append(relative.stem.lower())
                else:
                    try: destination = relative.relative_to(table_name.parent)
                    except ValueError: destination = relative
                    if relative.suffix.lower() == '.directb2s':
                        destination = PurePosixPath(table_name.stem+'.directb2s')
                    elif destination.parts[0].lower() == 'music':
                        destination = PurePosixPath('music', *destination.parts[1:])
                destination = safe_member(str(destination))
                key = str(destination).casefold()
                if key in destinations or any(key.startswith(old+'/') or old.startswith(key+'/') for old in destinations):
                    raise HTTPException(422, 'Dos archivos tendrían destinos incompatibles al preparar la mesa')
                destinations.add(key)
                files.append({'member': item.filename, 'destination': str(destination), 'size': item.file_size,
                              'crc': f'{item.CRC:08x}'})
            if required and (not roms or references and not set(references).intersection(roms)):
                needed = ', '.join(name+'.zip' for name in references) or 'la ROM ZIP indicada por el autor'
                raise HTTPException(422, 'Falta una ROM compatible para esta mesa: '+needed)
            return {'table': table_name.name, 'files': files, 'roms': roms, 'rom_candidates': references,
                    'has_backglass': bool(backglasses), 'requires_rom': required, 'raw_table': False}
    except (zipfile.BadZipFile, RuntimeError, OSError):
        raise HTTPException(422, 'El paquete de pinball no es un ZIP válido o está dañado') from None


@lru_cache(maxsize=64)
def cached_package(path, size, modified):
    return inspect_package(path)


def plan(library, game):
    path = library.safe_path(game['path'])
    stamp = path.stat()
    info = cached_package(str(path), stamp.st_size, stamp.st_mtime_ns)
    signature = hashlib.sha256(json.dumps([game['path'], path.stat().st_size, path.stat().st_mtime_ns, info], sort_keys=True).encode()).hexdigest()[:24]
    return {**info, 'engine': 'vpinball', 'signature': signature,
            'revision': str(path.stat().st_mtime_ns), 'size': path.stat().st_size,
            'download_url': f'/api/games/{game["id"]}/download',
            'platforms': {'windows': 'integrated', 'android': 'integrated'},
            'note': 'Windows: motor portátil. Android: motor incluido en GameClub 0.10.0+, Android 13+ ARM64; algunas mesas necesitan script standalone.'}
