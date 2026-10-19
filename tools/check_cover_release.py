"""Comprueba el APK release: ajustes sin cuentas y búsqueda real de carátulas."""
import argparse
import io
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--device', default='emulator-5554')
    parser.add_argument('--server', default='http://192.168.0.47:8001')
    parser.add_argument('--variant', choices=('mobile', 'tv'), required=True)
    parser.add_argument('--capture', type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    assert args.capture.parent.is_dir()
    args.capture.mkdir(exist_ok=True)
    prefix = [args.adb, '-s', args.device]
    def adb(*arguments):
        raw = subprocess.run([*prefix, *arguments], capture_output=True, check=True, timeout=40).stdout
        return raw.decode('utf-8', 'replace')
    def tree():
        xml = adb('exec-out', 'uiautomator', 'dump', '/dev/tty')
        if '<?xml' not in xml: raise RuntimeError(xml)
        return ET.fromstring(xml[xml.index('<?xml'):xml.index('</hierarchy>')+12])
    def label(node): return '\n'.join(filter(None, (node.get('content-desc'), node.get('text'), node.get('hint'))))
    def find(text, scroll=False, game=False):
        for _ in range(12 if scroll else 1):
            root = tree()
            view = next((node for node in root.iter('node') if node.get('scrollable') == 'true'), None)
            area = list(map(int, re.findall(r'\d+', view.get('bounds')))) if view is not None else None
            choices = []
            for node in root.iter('node'):
                if text not in label(node): continue
                if game and (node.get('class') == 'android.widget.EditText' or node.get('clickable') != 'true'): continue
                if game and not re.search(r'\bNES\b', label(node)): continue
                bounds = list(map(int, re.findall(r'\d+', node.get('bounds'))))
                if scroll and area and (bounds[1] < area[1] or bounds[3] > area[3]): continue
                choices.append(node)
            if choices:
                exact = [node for node in choices if text in label(node).splitlines()]
                return next((node for node in (exact or choices) if node.get('clickable') == 'true'), (exact or choices)[0])
            if scroll and area:
                x1,y1,x2,y2 = area
                adb('shell', 'input', 'swipe', str((x1+x2)//2), str(y1+(y2-y1)*4//5), str((x1+x2)//2), str(y1+(y2-y1)//5), '300')
        raise RuntimeError('No aparece '+text)
    def wait(text, **kwargs):
        end = time.monotonic()+120
        while time.monotonic() < end:
            try: return find(text, **kwargs)
            except RuntimeError: time.sleep(1)
        raise RuntimeError('Tiempo agotado: '+text)
    def tap(node):
        x1,y1,x2,y2 = map(int, re.findall(r'\d+', node.get('bounds')))
        adb('shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2)); time.sleep(.6)
    def capture(name):
        raw = subprocess.run([*prefix, 'exec-out', 'screencap', '-p'], capture_output=True, check=True).stdout
        Image.open(io.BytesIO(raw)).save(args.capture/(args.variant+'-'+name+'.png'))

    adb('shell', 'am', 'force-stop', 'com.gameclub.gameclub')
    adb('shell', 'am', 'start', '-n', 'com.gameclub.gameclub/.MainActivity')
    try:
        wait('GameClub · 0.9.0')
        tap(wait('Ajustes'))
        tap(find('Servidor', scroll=True))
        adb('shell', 'input', 'keyevent', 'KEYCODE_MOVE_END', *(['KEYCODE_DEL']*100))
        adb('shell', 'input', 'text', args.server)
        adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
        tap(find('Guardar y conectar', scroll=True))
        wait('Libretro → LaunchBox → GameTDB', scroll=True)
        labels = [label(node) for node in tree().iter('node')]
        assert not any('ScreenScraper' in text or 'Guardar cuenta' in text or 'Acceso API' in text for text in labels)
        capture('settings')
        tap(find('Biblioteca'))
        tap(wait('Buscar en la biblioteca'))
        adb('shell', 'input', 'text', '1942')
        adb('shell', 'input', 'keyevent', 'KEYCODE_BACK'); time.sleep(1)
        tap(wait('1942', game=True))
        tap(wait('Buscar carátula'))
        wait('Selecciona el juego correcto')
        wait('· Carátula')
        assert not any('Sin coincidencias' in label(node) for node in tree().iter('node'))
        capture('results')
        tap(find('Cancelar'))
        print(args.variant+': ajustes sin cuenta ni claves y resultados reales de Libretro correctos.', flush=True)
    finally:
        adb('shell', 'am', 'force-stop', 'com.gameclub.gameclub')


if __name__ == '__main__': main()
