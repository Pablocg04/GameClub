"""Comprueba ajustes y partida vertical del APK móvil instalado mediante su interfaz real."""
import argparse
import io
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from PIL import Image

parser=argparse.ArgumentParser()
parser.add_argument('--adb',required=True)
parser.add_argument('--device',default='emulator-5554')
parser.add_argument('--server',default='http://10.0.2.2:8692')
parser.add_argument('--capture',type=Path)
parser.add_argument('--game',default='Arkanoid')
parser.add_argument('--version',default='0.9.1')
args=parser.parse_args()
prefix=[args.adb,'-s',args.device]
def adb(*arguments):
    output=subprocess.run([*prefix,*arguments],capture_output=True,check=True,timeout=30).stdout
    try:return output.decode('utf-8')
    except UnicodeDecodeError:return output.decode('cp1252','replace')
def tree():
    xml=adb('exec-out','uiautomator','dump','/dev/tty')
    if '<?xml' not in xml:raise RuntimeError('UI Automator aún no está listo: '+xml)
    return ET.fromstring(xml[xml.index('<?xml'):xml.index('</hierarchy>')+12])
def label(node):return '\n'.join(filter(None,(node.get('content-desc'),node.get('text'),node.get('hint'))))
def find(text,scroll=False):
    for attempt in range(7 if scroll else 1):
        root=tree()
        view=next((node for node in root.iter('node') if node.get('scrollable')=='true'),None)
        area=list(map(int,re.findall(r'\d+',view.get('bounds')))) if view is not None else None
        matches=[]
        for node in root.iter('node'):
            if text.casefold() not in label(node).casefold():continue
            bounds=list(map(int,re.findall(r'\d+',node.get('bounds'))))
            if scroll and area and (bounds[1]<area[1] or bounds[3]>area[3]):continue
            matches.append(node)
        if matches:
            exact=[node for node in matches if any(line.casefold()==text.casefold() for line in label(node).splitlines())]
            choices=exact or matches
            return next((node for node in choices if node.get('clickable')=='true'),choices[0])
        if scroll:
            x1,y1,x2,y2=map(int,re.findall(r'\d+',view.get('bounds')))
            x=(x1+x2)//2;height=y2-y1
            adb('shell','input','swipe',str(x),str(y1+height*4//5),str(x),str(y1+height//5),'300')
    raise RuntimeError(f'No aparece {text!r}')
def tap(node):
    x1,y1,x2,y2=map(int,re.findall(r'\d+',node.get('bounds')))
    adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(.6)
def screen():
    return Image.open(io.BytesIO(subprocess.run([*prefix,'exec-out','screencap','-p'],capture_output=True,check=True).stdout)).convert('RGB')
def wait_label(text,timeout=60):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        try:return find(text)
        except RuntimeError:time.sleep(1)
    raise RuntimeError(f'Tiempo agotado: {text}')

adb('shell','am','force-stop','com.gameclub.gameclub')
adb('shell','am','start','-n','com.gameclub.gameclub/.MainActivity')
tap(wait_label('Ajustes'))
tap(find('Orientación del juego'))
tap(find('Vertical'))
field=find('Servidor',scroll=True)
tap(field)
adb('shell','input','keyevent','KEYCODE_MOVE_END',*(['KEYCODE_DEL']*100))
adb('shell','input','text',args.server)
fields=[node.get('text','') for node in tree().iter('node') if node.get('class')=='android.widget.EditText']
assert args.server in fields,f'La dirección no quedó en el campo: {fields}'
adb('shell','input','keyevent','KEYCODE_BACK')
tap(find('Guardar y conectar',scroll=True))
tap(wait_label('Biblioteca'))
tap(wait_label(args.game))
tap(wait_label('Jugar en GameClub'))
end=time.monotonic()+120
while time.monotonic()<end:
    activity=adb('shell','dumpsys','activity','activities')
    if any('ResumedActivity' in line and 'NativeGameActivity' in line for line in activity.splitlines()):break
    time.sleep(1)
else:raise RuntimeError('No arrancó MAME nativo')
time.sleep(13)
photo=screen()
if photo.width>photo.height:
    # Una variante móvil en un AVD de TV tiene ventana vertical con letterboxing.
    activity=adb('shell','dumpsys','activity','activities')
    bounds=re.search(r'bounds=Rect\((\d+), (\d+) - (\d+), (\d+)\)',activity)
    if bounds:photo=photo.crop(tuple(map(int,bounds.groups())))
assert photo.height>photo.width,'No se aplicó la preferencia vertical'
game=photo.crop((photo.width//4,0,photo.width*3//4,photo.height//2))
assert len(game.getcolors(game.width*game.height) or [])>2,'No hay vídeo de juego'
if args.capture:
    assert args.capture.parent.is_dir()
    photo.save(args.capture)
adb('shell','input','keyevent','KEYCODE_BACK');time.sleep(.5)
adb('shell','input','gamepad','keyevent','--duration','100','KEYCODE_DPAD_DOWN')
adb('shell','input','gamepad','keyevent','--duration','100','KEYCODE_BUTTON_A')
wait_label('GameClub · '+args.version)
print('APK móvil release: ajustes, orientación vertical persistida, vídeo y salida correctos.',flush=True)
