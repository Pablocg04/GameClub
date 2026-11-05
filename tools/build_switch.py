"""Compila GameClub NRO con devkitA64 y comprueba sus cabeceras/recursos."""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
from PIL import Image, ImageDraw, ImageFont


def resources(root, romfs):
    romfs.mkdir(parents=True, exist_ok=True)
    chars = list(range(32, 256)) + [0x20ac, 0x2014, 0x2022]
    fonts = [('pixel',root/'client/assets/fonts/PressStart2P-Regular.ttf',18,27),
             ('body',root/'switch-client/assets/Lato-Regular.ttf',24,31),
             ('small',root/'switch-client/assets/Lato-Regular.ttf',18,24)]
    for name, path, size, line in fonts:
        font = ImageFont.truetype(str(path), size)
        atlas = Image.new('RGBA', (1024, 1024))
        draw = ImageDraw.Draw(atlas)
        glyphs = {}
        for i, code in enumerate(chars):
            x,y=(i%21)*48,(i//21)*48
            char = chr(code)
            draw.text((x+2,y+font.getmetrics()[0]),char,font=font,fill='white',anchor='ls')
            glyphs[str(code)] = [x,y,min(48,math.ceil(font.getlength(char))+4),40,round(font.getlength(char))]
        atlas.save(romfs/(name+'.png'))
        (romfs/(name+'.json')).write_text(json.dumps({'line':line,'glyphs':glyphs}),encoding='utf-8')
    for name,path in [('OFL-PressStart2P.txt',root/'client/assets/fonts/OFL-PressStart2P.txt'),
                      ('OFL-Lato.txt',root/'switch-client/assets/OFL-Lato.txt'),
                      ('LICENSE-json.txt',root/'switch-client/vendor/LICENSE-json.txt')]:
        shutil.copy2(path,romfs/name)
    for path in (root/'switch-client/licenses').glob('*'):
        if path.is_file():
            shutil.copy2(path,romfs/path.name)
    icon=Image.new('RGB',(256,256),'#21123d');draw=ImageDraw.Draw(icon)
    art=['0001111111111000','0012222222222100','0122222222222210','0122322222242210',
         '0123332222424210','0122322112242210','0122222222222210','0012211111122100','0001100000011000']
    colors={'1':'#100b20','2':'#c5a1ff','3':'#100b20','4':'#ff79b8'}
    for y,row in enumerate(art):
        for x,c in enumerate(row):
            if c!='0':draw.rectangle((16+x*14,65+y*14,29+x*14,78+y*14),fill=colors[c])
    font=ImageFont.truetype(str(root/'client/assets/fonts/PressStart2P-Regular.ttf'),17)
    draw.text((17,210),'GAMECLUB',font=font,fill='#fff4dc')
    icon.save(romfs.parent/'icon.jpg',quality=95)


def verify(nro, elf, version):
    raw=nro.read_bytes();binary=elf.read_bytes()
    assert binary[:5]==b'\x7fELF\x02' and struct.unpack_from('<H',binary,18)[0]==183, 'No es ELF AArch64'
    assert raw[16:20]==b'NRO0', 'Falta cabecera NRO0'
    size=struct.unpack_from('<I',raw,24)[0]
    assert size>128 and size<len(raw) and raw[size:size+4]==b'ASET'
    for offset in (32,40,48):
        start,length=struct.unpack_from('<II',raw,offset)
        assert length>0 and start+length<=size, 'Segmento NRO fuera del ejecutable'
    icon_offset,icon_size=struct.unpack_from('<QQ',raw,size+8)
    assert icon_size>0 and size+icon_offset+icon_size<=len(raw)
    with Image.open(io.BytesIO(raw[size+icon_offset:size+icon_offset+icon_size])) as icon:
        assert icon.format=='JPEG' and icon.size==(256,256)
        icon.load()
    nacp_offset,nacp_size=struct.unpack_from('<QQ',raw,size+24)
    romfs_offset,romfs_size=struct.unpack_from('<QQ',raw,size+40)
    assert nacp_size==0x4000 and romfs_size>0
    nacp=raw[size+nacp_offset:size+nacp_offset+nacp_size]
    assert nacp[:512].split(b'\0')[0]==b'GameClub'
    assert nacp[0x3060:0x3070].split(b'\0')[0].decode()==version
    assert size+romfs_offset+romfs_size<=len(raw)
    for magic in (b'pixel.png',b'body.png',b'small.png',b'OFL-Lato.txt',b'LICENSE-json.txt'):
        assert magic in raw, magic
    return {'file':nro.name,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'version':version,'machine':'AArch64','format':'NRO0','romfs_size':romfs_size}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--devkitpro',type=Path)
    parser.add_argument('--resources-only',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    build=root/'switch-client/build';build.mkdir(parents=True,exist_ok=True)
    resources(root,build/'romfs')
    if args.resources_only:return
    sdk=(args.devkitpro or root/'dist/switch-toolchain/root/opt/devkitpro').resolve()
    compiler=sdk/'devkitA64/bin/aarch64-none-elf-g++.exe'
    if not compiler.is_file():raise RuntimeError('Ejecuta primero tools/prepare_switch_toolchain.py')
    env=os.environ.copy();env['DEVKITPRO']=sdk.as_posix()
    env['PATH']=str(sdk/'devkitA64/bin')+os.pathsep+str(sdk/'tools/bin')+os.pathsep+env['PATH']
    version=re.search(r'^version:\s*([^+\s]+)',(root/'client/pubspec.yaml').read_text(),re.M).group(1)
    common=['-std=gnu++17','-O2','-g','-Wall','-Wextra','-Wno-unused-parameter','-ffunction-sections','-fdata-sections',
        '-DGAMECLUB_SWITCH_VERSION="'+version+'"',
        '-march=armv8-a+crc+crypto','-mtune=cortex-a57','-mtp=soft','-fPIE','-ftls-model=local-exec','-D__SWITCH__','-D_REENTRANT','-DCURL_STATICLIB',
        '-isystem',str(sdk/'libnx/include'),'-isystem',str(sdk/'portlibs/switch/include'),'-isystem',str(sdk/'portlibs/switch/include/SDL2'),
        '-I'+str(root/'switch-client/vendor'),'-I'+str(root/'switch-client/src')]
    objects=[]
    for name in ('main','http','pinball'):
        obj=build/(name+'.o');objects.append(str(obj))
        subprocess.run([str(compiler),*common,'-c',str(root/f'switch-client/src/{name}.cpp'),'-o',str(obj)],env=env,check=True)
    obj=build/'miniz.o';objects.append(str(obj))
    subprocess.run([str(compiler),*common,'-DMINIZ_NO_ZLIB_APIS','-c',str(root/'switch-client/vendor/miniz/miniz.c'),'-o',str(obj)],env=env,check=True)
    elf=build/'GameClub.elf'
    libs=['-lSDL2_image','-lSDL2','-lcurl','-lpng','-ljpeg','-lwebp','-lz','-lEGL','-lglapi','-ldrm_nouveau','-lnx','-lm','-pthread']
    subprocess.run([str(compiler),*common,'-specs='+str(sdk/'libnx/switch.specs'),*objects,
        '-L'+str(sdk/'portlibs/switch/lib'),'-L'+str(sdk/'libnx/lib'),'-Wl,--start-group',*libs,'-Wl,--end-group',
        '-Wl,-Map,'+str(build/'GameClub.map'),'-o',str(elf)],env=env,check=True)
    nacp=build/'GameClub.nacp';nro=build/'GameClub.nro'
    subprocess.run([str(sdk/'tools/bin/nacptool.exe'),'--create','GameClub','GameClub',version,str(nacp)],check=True,env=env)
    subprocess.run([str(sdk/'tools/bin/elf2nro.exe'),str(elf),str(nro),'--icon='+str(build/'icon.jpg'),
        '--nacp='+str(nacp),'--romfsdir='+str(build/'romfs')],check=True,env=env)
    report=verify(nro,elf,version)
    (build/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
