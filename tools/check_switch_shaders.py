"""Compile/link the port's parsed mono shader sources with desktop OpenGL 4.3.

Requires the GLFX test's exported sections and a Windows SDL3 DLL. This checks
GLSL/program interfaces, not Switch driver behavior or emulation.
"""
import argparse
import ctypes as c
import json
import os
import re
import subprocess
from pathlib import Path
import sys


def expand(function, values):
    start, end = function.find('('), function.find(')')
    assert 0 <= start < end, function
    code = values.get(function[:start], '')
    assert code, function
    arguments = function[start+1:end]
    if arguments:
        for index, value in enumerate(arguments.split(',')):
            code = code.replace(f'%PARAM{index}%', value)
    return code


def preprocess(code):
    header, extensions, body = [], [], []
    for line in code.splitlines():
        if line.startswith('#version '):
            if int(line.split()[1]) > 430: line = '#version 430 core'
            header.extend((line, '#define SHADER_STANDALONE'))
        elif line.startswith('#extension '):
            extensions.append(line)
        else:
            body.append(line)
    return '\n'.join(header+extensions+body)+'\n'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser()
    parser.add_argument('--dll', required=True, type=Path)
    parser.add_argument('--sections', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--strict-compiler', required=True, type=Path, help='glslc, e.g. from the Android NDK')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    directory = os.add_dll_directory(str(args.dll.resolve().parent))
    sdl = c.CDLL(str(args.dll.resolve()))
    def api(name, result, *params):
        f = getattr(sdl, name); f.restype = result; f.argtypes = list(params); return f
    init = api('SDL_Init', c.c_bool, c.c_uint32)
    error = api('SDL_GetError', c.c_char_p)
    attribute = api('SDL_GL_SetAttribute', c.c_bool, c.c_int, c.c_int)
    window = api('SDL_CreateWindow', c.c_void_p, c.c_char_p, c.c_int, c.c_int, c.c_uint64)
    context = api('SDL_GL_CreateContext', c.c_void_p, c.c_void_p)
    address = api('SDL_GL_GetProcAddress', c.c_void_p, c.c_char_p)
    destroy_context = api('SDL_GL_DestroyContext', c.c_bool, c.c_void_p)
    destroy_window = api('SDL_DestroyWindow', None, c.c_void_p)
    assert init(0x20), error()
    attribute(17, 4); attribute(18, 3); attribute(21, 1)
    wnd = window(b'GameClub shader validation', 128, 128, 2 | 8)  # OpenGL, hidden.
    assert wnd, error()
    ctx = context(wnd)
    assert ctx, error()
    try:
        def gl(name, result, *params):
            pointer = address(name.encode()); assert pointer, name
            return c.WINFUNCTYPE(result, *params)(pointer)
        get_string = gl('glGetString', c.c_char_p, c.c_uint32)
        create_shader = gl('glCreateShader', c.c_uint32, c.c_uint32)
        shader_source = gl('glShaderSource', None, c.c_uint32, c.c_int, c.POINTER(c.c_char_p), c.POINTER(c.c_int))
        compile_shader = gl('glCompileShader', None, c.c_uint32)
        shader_info = gl('glGetShaderiv', None, c.c_uint32, c.c_uint32, c.POINTER(c.c_int))
        shader_log = gl('glGetShaderInfoLog', None, c.c_uint32, c.c_int, c.POINTER(c.c_int), c.c_void_p)
        create_program = gl('glCreateProgram', c.c_uint32)
        attach = gl('glAttachShader', None, c.c_uint32, c.c_uint32)
        link = gl('glLinkProgram', None, c.c_uint32)
        program_info = gl('glGetProgramiv', None, c.c_uint32, c.c_uint32, c.POINTER(c.c_int))
        program_log = gl('glGetProgramInfoLog', None, c.c_uint32, c.c_int, c.POINTER(c.c_int), c.c_void_p)
        delete_shader = gl('glDeleteShader', None, c.c_uint32)
        delete_program = gl('glDeleteProgram', None, c.c_uint32)
        renderer = get_string(0x1F01).decode(); version = get_string(0x1F02).decode()
        completed = []
        # These are the eight GLFX files loaded by a non-stereo VPX player.
        for name in ('UIShader', 'BasicShader', 'BallShader', 'DMDShader', 'FlasherShader', 'LightShader', 'FBShader', 'SMAA'):
            values = json.loads((args.sections/(name+'.glfx.json')).read_text(encoding='utf-8'))
            for technique in values['TECHNIQUES'].splitlines():
                if not technique or technique.startswith('//') or technique.count(':') < 3: continue
                parts = technique.split(':'); assert len(parts) in (4, 5), technique
                stages = [('vert', 0x8B31, 'VERTEX', parts[2]), ('frag', 0x8B30, 'FRAGMENT', parts[-1])]
                # VPX's UseGeometryShader() is false for this mono player;
                # geometry entries may be present but are not compiled/linked.
                program = create_program(); shaders = []
                try:
                    for extension, kind, section, function in stages:
                        source = preprocess(values.get('GLOBAL', '')+values.get(section, '')+'\n'+expand(function, values))
                        output = args.output/(name+'-'+parts[0]+'.'+extension)
                        output.write_text(source, encoding='utf-8')
                        versions = [int(v) for v in re.findall(r'^#version\s+(\d+)', source, re.M)]
                        assert versions and max(versions) <= 430, output
                        subprocess.run([str(args.strict_compiler), '--target-env=opengl', '-std=430core',
                                        '-fauto-bind-uniforms', '-fauto-map-locations', '-c', str(output),
                                        '-o', str(output.with_suffix('.'+extension+'.spv'))], check=True)
                        shader = create_shader(kind); shaders.append(shader)
                        raw = c.c_char_p(source.encode()); size = c.c_int(len(raw.value))
                        shader_source(shader, 1, c.byref(raw), c.byref(size)); compile_shader(shader)
                        status = c.c_int(); shader_info(shader, 0x8B81, c.byref(status))
                        if not status.value:
                            log = c.create_string_buffer(32768); shader_log(shader, len(log), None, log)
                            raise RuntimeError(str(output)+'\n'+log.value.decode(errors='replace'))
                        attach(program, shader)
                    link(program); status = c.c_int(); program_info(program, 0x8B82, c.byref(status))
                    if not status.value:
                        log = c.create_string_buffer(32768); program_log(program, len(log), None, log)
                        raise RuntimeError(name+':'+parts[0]+'\n'+log.value.decode(errors='replace'))
                    completed.append(name+':'+parts[0])
                finally:
                    delete_program(program)
                    for shader in shaders: delete_shader(shader)
        report = {'renderer': renderer, 'opengl': version, 'compiled_linked_programs':len(completed),
                  'techniques':completed, 'maximum_glsl':430, 'strict_compiler':str(args.strict_compiler),
                  'switch_hardware_tested':False}
        (args.output/'report.json').write_text(json.dumps(report,indent=2), encoding='utf-8')
        print(f'{len(completed)} programas GLSL compilados/enlazados; {renderer}, OpenGL {version}. Sin prueba en Switch.')
    finally:
        destroy_context(ctx); destroy_window(wnd); sdl.SDL_Quit(); directory.close()


if __name__ == '__main__': main()
