"""Prueba VPX incluido en GameClub desde la biblioteca normal de un Android ARM64.

Usa una mesa de ejemplo propia/oficial y un servidor temporal, sin app VPX externa.
"""
import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import httpx
from PIL import Image


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--adb',required=True)
    parser.add_argument('--device',default='emulator-5580')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--table',type=Path,required=True)
    parser.add_argument('--release',action='store_true',help='Comprueba estados mediante logcat sin run-as')
    parser.add_argument('--tv',action='store_true',help='Verifica la variante TV sin botonera táctil')
    parser.add_argument('--restart',action='store_true',help='Comprueba también recarga de la mesa en el mismo proceso')
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    assert args.root.parent.is_dir() and args.table.is_file()
    args.root.mkdir(exist_ok=True)
    project=Path(__file__).resolve().parents[1]
    prefix=[args.adb,'-s',args.device]
    def adb(*arguments):
        result=subprocess.run([*prefix,*arguments],capture_output=True,check=True,timeout=45)
        return result.stdout.decode('utf-8','replace')
    def tree():
        for _ in range(6):
            raw=adb('exec-out','uiautomator','dump','/dev/tty')
            if '<?xml' in raw:return ET.fromstring(raw[raw.index('<?xml'):raw.index('</hierarchy>')+12])
            time.sleep(.5)
        raise RuntimeError('Interfaz no disponible: '+raw)
    def label(node):return '\n'.join(filter(None,(node.get('content-desc'),node.get('text'),node.get('hint'))))
    def find(text,scroll=False):
        for _ in range(12 if scroll else 1):
            root=tree()
            choices=[node for node in root.iter('node') if text.casefold() in label(node).casefold()]
            if choices:
                exact=[node for node in choices if text.casefold() in [line.casefold() for line in label(node).splitlines()]]
                return next((node for node in (exact or choices) if node.get('clickable')=='true'),(exact or choices)[0])
            if scroll:
                node=next((node for node in root.iter('node') if node.get('scrollable')=='true'),None)
                if node is None:break
                x1,y1,x2,y2=map(int,re.findall(r'\d+',node.get('bounds')))
                adb('shell','input','swipe',str((x1+x2)//2),str(y1+(y2-y1)*4//5),str((x1+x2)//2),str(y1+(y2-y1)//5),'250')
        raise RuntimeError('No aparece '+text)
    def wait(text,timeout=90,**options):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            try:return find(text,**options)
            except RuntimeError:time.sleep(1)
        raise TimeoutError('No aparece '+text)
    def tap(node):
        x1,y1,x2,y2=map(int,re.findall(r'\d+',node.get('bounds')))
        adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(.5)
    def capture(name):
        raw=subprocess.run([*prefix,'exec-out','screencap','-p'],capture_output=True,check=True).stdout
        Image.open(io.BytesIO(raw)).save(args.root/name)
    with (args.root/'api.log').open('wb') as api_log:
        api=subprocess.Popen([sys.executable,str(project/'tools/pinball_fixture.py'),str(args.root),'--package',str(args.table),'--port','8697'],stdout=api_log,stderr=api_log)
        try:
            with httpx.Client(timeout=3) as client:
                end=time.monotonic()+30
                while time.monotonic()<end:
                    try:client.get('http://127.0.0.1:8697/health').raise_for_status();break
                    except httpx.HTTPError:time.sleep(.5)
                else:raise RuntimeError('El servidor local no arrancó')
                game=client.get('http://127.0.0.1:8697/api/games').raise_for_status().json()[0]
            report=f'files/pinball/saves/http___127_0_0_1_8697/{game["id"]}/session.json'
            def state():
                if args.release:
                    log=adb('logcat','-d','-v','raw','-s','GameClubPinball:I','*:S')
                    values=re.findall(r'state=(\w+)',log)
                    return values[-1] if values else None
                try:return json.loads(adb('shell','run-as','com.gameclub.gameclub','cat',report)).get('state')
                except (subprocess.CalledProcessError,json.JSONDecodeError):return None
            def wait_state(expected,timeout=360):
                end=time.monotonic()+timeout
                while time.monotonic()<end:
                    actual=state()
                    if actual==expected:print('Android integrado:',expected,flush=True);return
                    if actual=='error':raise RuntimeError(adb('logcat','-d','-v','raw','-s','GameClubPinball:I','*:S') if args.release else adb('shell','run-as','com.gameclub.gameclub','cat',report))
                    time.sleep(1)
                raise TimeoutError(f'No llega {expected}; estado {state()}')
            adb('reverse','tcp:8697','tcp:8697')
            adb('shell','am','force-stop','com.gameclub.gameclub')
            adb('logcat','-c')
            adb('shell','am','start','-n','com.gameclub.gameclub/.MainActivity')
            tap(wait('Ajustes'))
            tap(wait('Servidor',scroll=True))
            adb('shell','input','keyevent','KEYCODE_MOVE_END',*(['KEYCODE_DEL']*100))
            adb('shell','input','text','http://127.0.0.1:8697')
            adb('shell','input','keyevent','KEYCODE_BACK')
            tap(find('Guardar y conectar',scroll=True));time.sleep(2)
            tap(find('Biblioteca'))
            tap(wait(game['title']))
            tap(wait('Jugar pinball'))
            wait_state('menu')
            capture('menu.png')
            tap(wait('Continuar'))
            wait_state('running');time.sleep(5)
            capture('playing.png')
            playing_tree=tree()
            labels=[label(node) for node in playing_tree.iter('node')]
            def playing_control(text):
                return next(node for node in playing_tree.iter('node') if text.casefold() == label(node).casefold())
            if args.tv:
                assert not any('Flipper izquierdo' in value or 'Moneda' == value for value in labels),labels
                adb('shell','input','keyevent','KEYCODE_BUTTON_L1','KEYCODE_BUTTON_R1','KEYCODE_BUTTON_A')
            else:
                assert any('Flipper izquierdo' in value or 'Izq.' in value for value in labels),labels
                # Mantener pulsado comprueba que el motor recibe el control durante varios fotogramas.
                left=playing_control('Flipper izquierdo')
                x1,y1,x2,y2=map(int,re.findall(r'\d+',left.get('bounds')))
                x,y=str((x1+x2)//2),str((y1+y2)//2)
                holding=subprocess.Popen([*prefix,'shell','input','swipe',x,y,x,y,'4000'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                time.sleep(2);capture('left-held.png');holding.communicate(timeout=15)
                for name in ('Flipper izquierdo','Flipper derecho','Bola'):
                    try:tap(playing_control(name))
                    except StopIteration:
                        if name=='Flipper izquierdo':tap(playing_control('Izq.'))
                        elif name=='Flipper derecho':tap(playing_control('Der.'))
                        else:raise
            adb('shell','input','keycombination','KEYCODE_BUTTON_SELECT','KEYCODE_BUTTON_START')
            wait_state('menu')
            adb('shell','input','keyevent','KEYCODE_BUTTON_B')
            wait_state('running')
            adb('shell','input','keyevent','KEYCODE_BACK')
            wait_state('menu')
            if args.restart:
                tap(wait('Reiniciar mesa'))
                wait_state('running')
                capture('restarted.png')
                adb('shell','input','keyevent','KEYCODE_BACK')
                wait_state('menu')
            tap(wait('Guardar y salir'))
            wait_state('closed',timeout=30)
            wait('Biblioteca')
            print('VPX incluido: vídeo, controles, menú y salida a GameClub comprobados.',flush=True)
        finally:
            log=adb('logcat','-d','-v','threadtime')
            (args.root/'android.log').write_text(log,encoding='utf-8')
            try:capture('last.png')
            except Exception:pass
            api.terminate();api.wait(timeout=15)


if __name__=='__main__':main()
