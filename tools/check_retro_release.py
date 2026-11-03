"""Comprueba la biblioteca release en un emulador aislado, sin alterar juegos."""
import argparse
import re
import subprocess
import time
from pathlib import Path
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--device', required=True)
    parser.add_argument('--variant', choices=('mobile', 'tv'), required=True)
    parser.add_argument('--capture', type=Path, required=True)
    args = parser.parse_args()
    assert args.device.startswith('emulator-'), 'Usa un emulador de pruebas aislado'
    args.capture.mkdir(parents=True, exist_ok=True)
    prefix = [args.adb, '-s', args.device]

    def adb(*command):
        return subprocess.run([*prefix, *command], capture_output=True,
                              check=True, timeout=40).stdout

    def tree():
        raw = adb('exec-out', 'uiautomator', 'dump', '/dev/tty').decode('utf-8', 'replace')
        if '<?xml' not in raw:
            raise RuntimeError(raw)
        return ET.fromstring(raw[raw.index('<?xml'):raw.index('</hierarchy>') + 12])

    def label(node):
        return '\n'.join(filter(None, (node.get('text'), node.get('content-desc'), node.get('hint'))))

    def wait(text, *, exact=False, clickable=False):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                nodes = tree().iter('node')
            except RuntimeError:
                time.sleep(.5)
                continue
            for node in nodes:
                matches = text == label(node) if exact else text in label(node)
                if matches and (not clickable or node.get('clickable') == 'true'):
                    return node
            time.sleep(.5)
        raise RuntimeError('No aparece ' + text)

    def tap(text, **kwargs):
        node = wait(text, clickable=True, **kwargs)
        x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
        adb('shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2))

    def capture(name):
        time.sleep(.5)
        (args.capture / f'{args.variant}-{name}.png').write_bytes(adb('exec-out', 'screencap', '-p'))
        print(f'{args.variant}: {name}', flush=True)

    def reveal(text):
        for _ in range(8):
            snapshot = tree()
            if any(text in label(n) for n in snapshot.iter('node')):
                return
            views = [n for n in snapshot.iter('node') if n.get('scrollable') == 'true']
            assert views, 'No hay una vista desplazable para ' + text
            view = views[0]
            x1, y1, x2, y2 = map(int, re.findall(r'\d+', view.get('bounds')))
            adb('shell', 'input', 'swipe', str((x1+x2)//2), str(y1+(y2-y1)*4//5),
                str((x1+x2)//2), str(y1+(y2-y1)//5), '350')
        raise RuntimeError('No se puede desplazar hasta ' + text)

    adb('shell', 'am', 'force-stop', 'com.gameclub.gameclub')
    adb('shell', 'am', 'start', '-n', 'com.gameclub.gameclub/.MainActivity')
    wait('GAMECLUB')
    wait('MAME\n', clickable=True)
    if args.variant == 'tv':
        assert not any('Visual Pinball' in label(n) for n in tree().iter('node'))
    capture('library')
    tap('Buscar en la biblioteca')
    adb('shell', 'input', 'text', '1942')
    adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
    wait('MAME\n1942', exact=True, clickable=True)
    capture('search')
    tap('MAME\n1942', exact=True)
    wait('Jugar en GameClub')
    reveal('Capturas del juego')
    capture('detail')
    adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
    # Android puede restaurar el teclado del buscador al cerrar la ficha.
    # Se oculta para recuperar la navegación inferior de la biblioteca.
    if not any(label(n) == 'Favoritos' and n.get('clickable') == 'true'
               for n in tree().iter('node')):
        adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
    tap('Favoritos', exact=True)
    wait('Favoritos', exact=True)
    capture('favorites')
    if args.variant == 'tv':
        # LB/RB: el recorrido del mando funciona en el APK real.
        adb('shell', 'input', 'gamepad', 'keyevent', 'KEYCODE_BUTTON_R1')
    else:
        tap('Ajustes', exact=True)
    reveal('Conexión con tu Raspberry')
    capture('settings')
    if args.variant == 'tv':
        adb('shell', 'input', 'gamepad', 'keyevent', 'KEYCODE_BUTTON_R1')
    else:
        tap('Biblioteca', exact=True)
    wait('MAME\n1942', exact=True, clickable=True)
    if args.variant == 'mobile':
        adb('shell', 'settings', 'put', 'system', 'accelerometer_rotation', '0')
        adb('shell', 'settings', 'put', 'system', 'user_rotation', '1')
        time.sleep(2)
        wait('MAME\n1942', exact=True, clickable=True)
        assert any(n.get('class') == 'android.widget.EditText' and n.get('text') == '1942'
                   for n in tree().iter('node')), 'La búsqueda debe conservarse al girar'
        capture('landscape')
        adb('shell', 'settings', 'put', 'system', 'user_rotation', '0')
    else:
        # Select enfoca la búsqueda; al volver a la cuadrícula, A abre la ficha.
        adb('shell', 'input', 'gamepad', 'keyevent', 'KEYCODE_BUTTON_SELECT')
        assert any(n.get('class') == 'android.widget.EditText' and n.get('focused') == 'true'
                   for n in tree().iter('node')), 'Select debe enfocar el buscador'
        adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
        time.sleep(.5)
        adb('shell', 'input', 'keyevent', 'KEYCODE_DPAD_DOWN')
        time.sleep(.5)
        adb('shell', 'input', 'keyevent', 'KEYCODE_DPAD_DOWN')
        time.sleep(.5)
        adb('shell', 'input', 'gamepad', 'keyevent', 'KEYCODE_BUTTON_A')
        wait('Jugar en GameClub')
        reveal('Capturas del juego')
        capture('controller-detail')
        adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
    print(f'{args.variant}: búsqueda, ficha, favoritos, ajustes y navegación correctos.', flush=True)


if __name__ == '__main__':
    main()
