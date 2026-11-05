"""Genera el NRO VPX/PinMAME y un ZIP de SD comprobado, sin mesas ni ROMs."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zipfile
from PIL import Image
import io
from build_switch_pinball import ROOT, PORT, DEPS, SDK
from build_switch import verify as verify_launcher


def verify_engine(path, version):
    raw = path.read_bytes()
    assert raw[16:20] == b'NRO0'
    assert ('GameClub '+version+': VPX/PinMAME').encode() in raw, 'El motor no fue recompilado para esta versión'
    size = struct.unpack_from('<I', raw, 24)[0]
    assert 128 < size < len(raw) and raw[size:size+4] == b'ASET'
    for offset in (32, 40, 48):
        start, length = struct.unpack_from('<II', raw, offset)
        assert length > 0 and start + length <= size
    icon_offset, icon_size = struct.unpack_from('<QQ', raw, size+8)
    assert size+icon_offset+icon_size <= len(raw)
    with Image.open(io.BytesIO(raw[size+icon_offset:size+icon_offset+icon_size])) as icon:
        assert icon.format == 'JPEG' and icon.size == (256, 256)
        icon.load()
    nacp_offset, nacp_size = struct.unpack_from('<QQ', raw, size+24)
    assert nacp_size == 0x4000 and size+nacp_offset+nacp_size <= len(raw)
    nacp = raw[size+nacp_offset:size+nacp_offset+nacp_size]
    assert nacp[:512].split(b'\0')[0] == b'GameClub Pinball'
    assert nacp[0x3060:0x3070].split(b'\0')[0].decode() == version
    return {'file':path.name, 'size':len(raw), 'sha256':hashlib.sha256(raw).hexdigest(),
            'format':'NRO0', 'machine':'AArch64', 'version':version,
            'bss_size':struct.unpack_from('<I', raw, 56)[0], 'hardware_tested':False}


def main():
    version = re.search(r'^version:\s*([^+\s]+)', (ROOT/'client/pubspec.yaml').read_text(), re.M).group(1)
    build = DEPS/'vpx-build'
    elf = build/'GameClubPinball.elf'
    header = elf.read_bytes()[:64]
    assert header[:5] == b'\x7fELF\x02' and struct.unpack_from('<H', header, 18)[0] == 183
    assert elf.stat().st_size > 1024*1024, 'El enlace del motor no está terminado'
    symbols = subprocess.check_output([str(SDK/'devkitA64/bin/aarch64-none-elf-nm.exe'),
                                       '-C', str(elf)], text=True)
    assert 'std::thread::detach()' not in symbols, 'El motor todavía usa detach, no implementado por el SDK Horizon'
    env = os.environ.copy()
    env['DEVKITPRO'] = SDK.as_posix()
    env['PATH'] = str(SDK/'devkitA64/bin')+os.pathsep+env['PATH']
    nro = build/'GameClubPinball.nro'
    nacp = build/'GameClubPinball.nacp'
    icon = ROOT/'switch-client/build/icon.jpg'
    subprocess.run([str(SDK/'tools/bin/nacptool.exe'), '--create', 'GameClub Pinball', 'GameClub', version, str(nacp)], env=env, check=True)
    subprocess.run([str(SDK/'tools/bin/elf2nro.exe'), str(elf), str(nro), '--icon='+str(icon), '--nacp='+str(nacp)], env=env, check=True)
    report = verify_engine(nro, version)
    (build/'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    launcher = ROOT/'switch-client/build/GameClub.nro'
    verify_launcher(launcher, ROOT/'switch-client/build/GameClub.elf', version)
    stage = ROOT/'dist'/('switch-pinball-sd-'+version)
    app = stage/'switch/gameclub'
    engine = app/'pinball'
    engine.mkdir(parents=True, exist_ok=True)
    shutil.copy2(nro, engine/nro.name)
    shutil.copy2(launcher, app/'GameClub-Switch.nro')
    blocked = {'.vpx', '.vpxz', '.zip', '.7z', '.nv', '.sta', '.rom', '.exe', '.dll', '.so', '.apk', '.elf'}
    def tree(source, dest):
        for p in source.rglob('*'):
            if p.is_file() and p.suffix.lower() not in blocked and not p.is_symlink():
                output = dest/p.relative_to(source)
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, output)
    source = DEPS/'vpinball'
    tree(source/'src/assets', engine/'assets')
    tree(source/'scripts', engine/'scripts')
    tree(source/'src/shaders/hlsl_glsl', engine/'shaders-10.8.1')
    # Assets from the same official VPX revision used by the Android package.
    registry = json.loads((ROOT/'client/platform-config/pinball_runtime.json').read_text())
    assets = ROOT/'client/native/vendor/pinball/assets/pinball'
    for name, entry in registry['assets'].items():
        if name.startswith('plugins/flexdmd/assets/'):
            raw = (assets/name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == entry['sha256'] and len(raw) == entry['size']
            dest = engine/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
    tree(ROOT/'switch-client/licenses', engine/'licenses/toolchain')
    tree(PORT/'licenses', engine/'licenses/port')
    for name in ('vpinball', 'pinmame-vpx', 'libwinevbs', 'freeimage', 'SDL3', 'SDL_image', 'SDL_ttf'):
        base = DEPS/name
        for p in base.rglob('*'):
            if not p.is_file() or '.git' in p.parts:
                continue
            if p.name.lower().startswith(('license', 'copying', 'copyright')):
                dest = engine/'licenses'/name/p.relative_to(base)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
    for name in ('SWITCH.md', 'SWITCH_PINBALL.md', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name, stage/name)
    shutil.copy2(PORT/'upstream.json', engine/'upstream.json')
    (engine/'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    files = {}
    for p in sorted(stage.rglob('*')):
        if p.is_file() and p.name != 'CONTENIDO-SHA256.json':
            assert p.suffix.lower() not in blocked
            with p.open('rb') as f: digest = hashlib.file_digest(f, 'sha256').hexdigest()
            files[p.relative_to(stage).as_posix()] = {'size':p.stat().st_size, 'sha256':digest}
    (stage/'CONTENIDO-SHA256.json').write_text(json.dumps(files, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = ROOT/'dist'/f'GameClub-Switch-Pinball-{version}.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip:
        for p in sorted(stage.rglob('*')):
            if p.is_file():zip.write(p, p.relative_to(stage).as_posix())
    with zipfile.ZipFile(archive) as zip:
        assert zip.testzip() is None
        for name, entry in files.items():
            raw = zip.read(name)
            assert len(raw) == entry['size'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
    print(json.dumps(report, indent=2))
    print(archive, archive.stat().st_size)


if __name__ == '__main__':
    main()
