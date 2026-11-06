"""Compilación nativa de VPX/PinMAME para libnx; fuentes y parches fijados.

Las fuentes externas, SDK y objetos quedan en dist/. No modifica las ROMs,
las instalaciones del sistema ni los paquetes GameClub ya publicados.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT/'switch-pinball'
DEPS = ROOT/'dist/switch-ports'
SDK = ROOT/'dist/switch-toolchain/root/opt/devkitpro'
PREFIX = DEPS/'prefix'
LOCK = json.loads((PORT/'upstream.json').read_text())


def executable(name, relative):
    found = shutil.which(name)
    if found:
        return found
    base = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Microsoft Visual Studio'
    options = sorted(base.glob('*/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/'+relative))
    if not options:
        raise RuntimeError('No se encuentra '+name)
    return str(options[-1])


def run(command, env=None, cwd=ROOT):
    subprocess.run([str(x) for x in command], cwd=cwd, env=env, check=True)


def prepare_source(name):
    entry = LOCK[name]
    source = DEPS/entry.get('directory', name)
    if not source.exists():
        source.mkdir(parents=True)
        run(['git', 'init', source])
        run(['git', 'remote', 'add', 'origin', entry['repository']], cwd=source)
        run(['git', 'fetch', '--depth', '1', 'origin', entry['commit']], cwd=source)
        run(['git', 'checkout', '--detach', entry['commit']], cwd=source)
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if actual != entry['commit']:
        raise RuntimeError(f'{source}: revisión distinta de la fijada; usa una carpeta nueva para conservar los cambios')
    patch = PORT/'patches'/(name+'.patch')
    if patch.exists() and patch.stat().st_size:
        applied = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=source,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not applied:
            run(['git', 'apply', '--check', patch], cwd=source)
            run(['git', 'apply', patch], cwd=source)
    return source


def prepare_headers():
    for name, source in [('libwinevbs', DEPS/'libwinevbs/include'),
                         ('pinmame', DEPS/LOCK['pinmame'].get('directory', 'pinmame')/'src/libpinmame')]:
        dest = PREFIX/'include'/name
        dest.mkdir(parents=True, exist_ok=True)
        files = list(source.glob('*.h')) if name == 'libwinevbs' else [source/'libpinmame.h', source/'PinMAMEPlugin.h']
        for path in files:
            shutil.copy2(path, dest/path.name)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser()
    parser.add_argument('component', choices=['all', 'pinmame', 'libwinevbs', 'SDL3', 'SDL_image', 'SDL_ttf', 'freeimage', 'vpinball'])
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--objects-only', action='store_true', help='Compila VPX sin enlazar mientras se preparan sus dependencias')
    args = parser.parse_args()
    assert 1 <= args.jobs <= 16
    cmake = executable('cmake', 'CMake/bin/cmake.exe')
    ninja = executable('ninja', 'Ninja/ninja.exe')
    env = os.environ.copy()
    env['DEVKITPRO'] = SDK.as_posix()
    env['PATH'] = str(SDK/'devkitA64/bin')+os.pathsep+env['PATH']
    if not (SDK/'devkitA64/bin/aarch64-none-elf-g++.exe').is_file():
        raise RuntimeError('Ejecuta tools/prepare_switch_toolchain.py primero')
    DEPS.mkdir(exist_ok=True, parents=True)
    components = ['pinmame', 'libwinevbs', 'SDL3', 'SDL_image', 'SDL_ttf', 'freeimage', 'vpinball'] if args.component == 'all' else [args.component]
    build_names = {'pinmame':'pinmame-vpx', 'SDL3':'sdl3', 'SDL_image':'sdl-image', 'SDL_ttf':'sdl-ttf', 'libwinevbs':'winevbs', 'vpinball':'vpx'}
    for name in components:
        source = prepare_source(name)
        build_name = build_names.get(name, name)
        build = DEPS/(build_name+'-build')
        options = ['-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED=OFF', '-DBUILD_STATIC=ON']
        target = None
        if name == 'pinmame':
            text = (source/'cmake/libpinmame/CMakeLists.txt').read_text()
            text = text.replace('if(IPO_SUPPORTED AND NOT MINGW)', 'if(IPO_SUPPORTED AND NOT MINGW AND NOT NINTENDO_SWITCH)')
            text += '\nset_source_files_properties(src/cpu/m6809/m6809.c PROPERTIES COMPILE_OPTIONS "-O1;-fno-tree-pta")\n'
            (source/'CMakeLists.txt').write_text(text, encoding='utf-8')
            options += ['-DPLATFORM=switch', '-DARCH=arm64', '-DPINMAME_JIT_ASMJIT=OFF', '-DPINMAME_P2K=OFF', '-DPINMAME_SPIKE1=OFF']
            target = 'pinmame_static'
        elif name == 'libwinevbs':
            bison = DEPS/'host-tools/win_bison.exe'
            if not bison.is_file():
                raise RuntimeError('Falta Bison 3.8.2 en dist/switch-ports/host-tools/win_bison.exe')
            options += ['-DPLATFORM=switch', '-DARCH=arm64', '-DBISON_EXECUTABLE='+bison.as_posix()]
            target = 'winevbs_static'
        elif name == 'freeimage':
            options += ['-DPLATFORM=switch', '-DARCH=arm64']
            target = 'freeimage_static'
        elif name == 'SDL3':
            options += ['-DSDL_SHARED=OFF', '-DSDL_STATIC=ON', '-DSDL_TEST_LIBRARY=OFF',
                        '-DHAVE_SIGACTION=0', '-DHAVE_PTHREAD_SETNAME_NP=0', '-DHAVE_ICONV=0', '-DHAVE_FDATASYNC=0',
                        '-DICONV_IN_LIBC=0', '-DICONV_IN_LIBICONV=0']
        elif name == 'SDL_image':
            options += ['-DBUILD_SHARED_LIBS=OFF', '-DSDLIMAGE_SAMPLES=OFF', '-DSDLIMAGE_TESTS=OFF',
                        '-DSDLIMAGE_AVIF=OFF', '-DSDLIMAGE_JXL=OFF', '-DSDLIMAGE_TIF=OFF', '-DSDLIMAGE_WEBP=OFF',
                        '-DSDLIMAGE_VENDORED=OFF', '-DSDLIMAGE_DEPS_SHARED=OFF']
        elif name == 'SDL_ttf':
            options += ['-DBUILD_SHARED_LIBS=OFF', '-DSDLTTF_SAMPLES=OFF', '-DSDLTTF_VENDORED=OFF',
                        '-DSDLTTF_HARFBUZZ=ON', '-DSDLTTF_PLUTOSVG=OFF']
        elif name == 'vpinball':
            prepare_headers()
            shutil.copy2(PORT/'cmake/vpinball.cmake', source/'CMakeLists.txt')
        command = [cmake, '-S', source, '-B', build, '-G', 'Ninja', '-DCMAKE_MAKE_PROGRAM='+ninja,
                   '-DCMAKE_TOOLCHAIN_FILE='+(PORT/'cmake/libnx.cmake').as_posix(),
                   '-DDEVKITPRO='+SDK.as_posix(), '-DCMAKE_INSTALL_PREFIX='+PREFIX.as_posix(),
                   '-DCMAKE_PREFIX_PATH='+PREFIX.as_posix()+';'+(SDK/'portlibs/switch').as_posix(),
                   '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', *options]
        log_path = DEPS/(build_name+'-build.log')
        print('Compilando '+name+' → '+str(log_path), flush=True)
        with log_path.open('w', encoding='utf-8') as log:
            subprocess.run([str(x) for x in command], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            if name == 'vpinball' and args.objects_only:
                lines = subprocess.check_output([ninja, '-C', str(build), '-t', 'targets', 'all'], env=env, text=True)
                targets = [l.split(': ')[0] for l in lines.splitlines() if '.obj:' in l and
                           any('CMakeFiles/'+t+'.dir/' in l for t in ('vpinball', 'PinMAMEPlugin', 'B2SPlugin', 'FlexDMDPlugin', 'ScoreViewPlugin'))]
                subprocess.run([ninja, '-C', str(build), '-j'+str(args.jobs), *targets], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            else:
                command = [cmake, '--build', str(build), '--parallel', str(args.jobs)]
                if target:
                    command += ['--target', target]
                subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            if name.startswith('SDL'):
                subprocess.run([cmake, '--install', str(build)], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        print('Compilado '+name, flush=True)


if __name__ == '__main__':
    main()
