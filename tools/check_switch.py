"""Prueba el cliente nativo contra una API aislada con datos propios y genera vistas."""
import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import subprocess
import threading
import urllib.parse
import zipfile
import copy
from PIL import Image, ImageDraw


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    folder=(args.directory or root/'dist/switch-checks').resolve()
    folder.mkdir(parents=True,exist_ok=True)
    tests=root/'switch-client/build-host/Release/gameclub_switch_test.exe'
    preview=root/'switch-client/build-host/Release/gameclub_switch_preview.exe'
    assert tests.is_file() and preview.is_file(), 'Compila primero el proyecto CMake de switch-client'
    counts=Counter()
    content=b'GC01'  # Fixture propio de transporte; no es una ROM.
    image=Image.new('RGB',(180,240),'#8549ed');draw=ImageDraw.Draw(image)
    draw.rectangle((20,40,159,170),fill='#100b20');draw.rectangle((35,70,144,130),fill='#75e5ca')
    draw.text((40,195),'GAMECLUB',fill='#fff4dc')
    buffer=io.BytesIO();image.save(buffer,format='JPEG');cover=buffer.getvalue()
    games=[{'id':s,'title':t,'system_id':s,'filename':s+'.zip','size':4,'revision':'1',
            'favorite':s=='nes','cover_url':'/api/games/'+s+'/cover'}
           for s,t in [('nes','Mi clásico NES'),('gba','Aventura GBA'),('mame','Arcade de prueba')]]
    pinball_buffer=io.BytesIO()
    with zipfile.ZipFile(pinball_buffer,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('Folder/Fixture.vpx',bytes.fromhex('d0cf11e0a1b11ae1')+b'GameClub fixture' * 300000)
        z.writestr('Folder/fixture.zip',b'GameClub transport fixture, not a ROM')
    pinball=pinball_buffer.getvalue()
    games.append({'id':'pinball','title':'Mesa de prueba','system_id':'vpinball','filename':'Fixture.zip',
                  'size':len(pinball),'revision':'1','favorite':False,'cover_url':'/api/games/pinball/cover'})
    with zipfile.ZipFile(io.BytesIO(pinball)) as z:
        pinball_manifest={'table':'Fixture.vpx','signature':'fixture123','revision':'1','size':len(pinball),
            'raw_table':False,'files':[{'member':i.filename,'destination':'Fixture.vpx' if i.filename.endswith('.vpx') else 'pinmame/roms/fixture.zip',
                                      'size':i.file_size,'crc':f'{i.CRC:08x}'} for i in z.infolist()]}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def reply(self,status,value,kind='application/json'):
            raw=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            counts[self.path]+=1
            if self.headers.get('Authorization')!='Bearer fixture-token':return self.reply(401,{'detail':'Token incorrecto'})
            url=urllib.parse.urlparse(self.path)
            if url.path=='/api/games':return self.reply(200,games)
            if url.path=='/api/games/cover-039/cover':return self.reply(200,b'broken fixture','image/jpeg')
            if url.path.endswith('/cover'):return self.reply(200,cover,'image/jpeg')
            if url.path.endswith('/pinball'):
                value=copy.deepcopy(pinball_manifest)
                if '/pinball-evil/' in url.path:value['files'][0]['destination']='../escape.vpx'
                if '/pinball-crc/' in url.path:value['files'][0]['crc']='ffffffff'
                return self.reply(200,value)
            if url.path.startswith('/api/games/pinball') and url.path.endswith('/download'):
                return self.reply(200,pinball,'application/zip')
            if url.path.endswith('/download') or url.path=='/api/mame/download':return self.reply(200,content,'application/octet-stream')
            if url.path.endswith('/arcade/cores'):
                malicious='/evil/' in url.path
                return self.reply(200,{'candidates':[{'core':'mame2003_plus','signature':'test123','game_code':'fixture',
                    'files':[{'path':'fixture.zip','destination':'../escape.zip' if malicious else 'fixture.zip','size':4},
                             {'path':'parent.zip','destination':'parent.zip','size':4}]}]})
            return self.reply(404,{})
        def do_PATCH(self):
            counts['PATCH']+=1
            if self.headers.get('Authorization')!='Bearer fixture-token':return self.reply(401,{})
            data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            for g in games:
                if self.path=='/api/games/'+g['id']:g['favorite']=data['favorite'];return self.reply(200,g)
            return self.reply(404,{})

    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}'
    # Cada ejecución usa un espacio nuevo; no toca preferencias ni guardados reales.
    import tempfile
    data=Path(tempfile.mkdtemp(prefix='run-',dir=folder))
    try:
        subprocess.run([str(tests),url,str(data)],check=True)
        threads=tests.with_name('gameclub_switch_threads_test.exe')
        if threads.is_file():
            subprocess.run([str(threads)],check=True,timeout=30)
        formats=tests.with_name('gameclub_switch_format_test.exe')
        if formats.is_file():
            subprocess.run([str(formats)],check=True,timeout=30)
        shaders=tests.with_name('gameclub_switch_glfx_test.exe')
        if shaders.is_file():
            subprocess.run([str(shaders),str(root/'dist/switch-ports/vpinball/src/shaders/hlsl_glsl'),
                            str(folder/'glfx')],check=True,timeout=30)
        assert counts['/api/games/nes/download']==1, 'La caché válida no debe volver a descargar'
        shots=[]
        for name,extra in [('library',[]),('favorites',['--tab','1']),('systems',['--tab','2']),
                           ('settings',['--tab','3']),('detail',['--detail','nes']),('search',['--query','clásico']),
                           ('pinball-detail',['--detail','pinball'])]:
            destination=folder/(name+'.png')
            subprocess.run([str(preview),'--headless','--frames','90','--assets',str(root/'switch-client/build/romfs'),
                            '--data-dir',str(data),'--screenshot',str(destination),*extra],check=True)
            picture=Image.open(destination);assert picture.size==(1280,720)
            shots.append(str(destination))
        assert counts['/api/games']>=7
        # Fill beyond cache capacity, then revisit resident pages. Reverse IDs
        # expose eviction by alphabetical key rather than by recent use.
        games.extend({'id':f'cover-{39-i:03}', 'title':f'A Cover {i:03}', 'system_id':'nes',
                      'filename':f'Cover{i}.nes', 'size':4, 'revision':'1', 'favorite':False,
                      'cover_url':None if i==1 else f'/api/games/cover-{39-i:03}/cover'} for i in range(40))
        subprocess.run([str(preview),'--headless','--frames','480','--exercise-covers',
                        '--assets',str(root/'switch-client/build/romfs'),'--data-dir',str(data)],check=True,timeout=45)
        navigation=json.loads((data/'launcher-performance.json').read_text())
        assert navigation['cover_uploads']>=30, navigation
        assert navigation['cover_uploads']<=44 and navigation['cover_jobs']<=60, navigation
        assert navigation['cached_textures']<=32, navigation
        assert counts['/api/games/cover-039/cover']==1, 'No repetir una carátula dañada cada frame'
        assert counts['/api/games/cover-038/cover']==0, 'No solicitar carátulas ausentes'
        print('Navegación tras llenar caché:',navigation,flush=True)
        (folder/'report.json').write_text(json.dumps({'api':url,'requests':dict(counts),'screenshots':shots,
            'navigation':navigation,'physical_switch_tested':False},ensure_ascii=False,indent=2),encoding='utf-8')
        print('API, aislamiento, descargas, guardados, MAME, VPX y siete vistas nativas comprobados.',flush=True)
    finally:
        server.shutdown();server.server_close();thread.join()


if __name__=='__main__':main()
