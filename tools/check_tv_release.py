"""Comprueba el APK instalado usando mandos ADB y la interfaz normal de biblioteca."""
import argparse
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import io
import re
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", required=True)
    parser.add_argument("--device", default="emulator-5554")
    parser.add_argument("--server")
    parser.add_argument("--game",default="Arkanoid")
    parser.add_argument("--version",default="0.10.1")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    def adb(*command):
        output = subprocess.run([args.adb, "-s", args.device, *command], check=True,
                                capture_output=True, timeout=30).stdout
        try:
            return output.decode("utf-8")
        except UnicodeDecodeError:
            return output.decode("cp1252", errors="replace")

    def key(name):
        adb("shell", "input", "gamepad", "keyevent", name)
        time.sleep(.5)

    def labels():
        xml = adb("exec-out", "uiautomator", "dump", "/dev/tty")
        if '<?xml' not in xml:return []
        root = ET.fromstring(xml[xml.index("<?xml"):xml.index("</hierarchy>") + 12])
        return [node.get("content-desc") or node.get("text") or node.get("hint", "") for node in root.iter("node")]

    def wait_for(text, timeout=120):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            current = labels()
            if 'Set up Google TV' in current and 'Cancel' in current:
                tap_label('Cancel',False)
                adb('shell','am','start','-n','com.gameclub.gameclub/.MainActivity')
                continue
            if any(text in label for label in current):
                print("OK:", text, flush=True)
                return
            time.sleep(1)
        raise RuntimeError(f"No aparece {text!r}: {current}")

    def wait_library_ready(timeout=30):
        end=time.monotonic()+timeout
        ready=0
        while time.monotonic()<end:
            xml=adb('exec-out','uiautomator','dump','/dev/tty')
            if '<?xml' in xml:
                root=ET.fromstring(xml[xml.index('<?xml'):xml.index('</hierarchy>')+12])
                enabled=any('Escanear biblioteca' in (node.get('content-desc','')+node.get('text',''))
                            and node.get('enabled')=='true' for node in root.iter('node'))
                loading=any(node.get('class')=='android.widget.ProgressBar' for node in root.iter('node'))
                ready=ready+1 if enabled and not loading else 0
                if ready>=2:return
            time.sleep(.2)
        raise RuntimeError('La biblioteca no terminó de recuperar sus controles')

    def tap_label(text, scrolling=True):
        for attempt in range(8):
            xml=adb('exec-out','uiautomator','dump','/dev/tty')
            if '<?xml' not in xml:time.sleep(1);continue
            root=ET.fromstring(xml[xml.index('<?xml'):xml.index('</hierarchy>')+12])
            view=next((node for node in root.iter('node') if node.get('scrollable')=='true'),None)
            area=list(map(int,re.findall(r'\d+',view.get('bounds')))) if view is not None else None
            for node in root.iter('node'):
                label=' '.join((node.get('content-desc',''),node.get('text',''),node.get('hint','')))
                if text in label:
                    x1,y1,x2,y2=map(int,re.findall(r'\d+',node.get('bounds')))
                    if scrolling and area and (y1<area[1] or y2>area[3]):continue
                    adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(.6);return
            adb('shell','input','swipe','640','530','640','240','300')
        raise RuntimeError('No aparece '+text)

    adb("shell", "am", "force-stop", "com.gameclub.gameclub")
    adb("shell", "am", "start", "-n", "com.gameclub.gameclub/.MainActivity")
    if args.server:
        wait_for('GameClub · '+args.version)
        tap_label('Ajustes',False)
        tap_label('Servidor')
        adb('shell','input','keyevent','KEYCODE_MOVE_END',*(['KEYCODE_DEL']*100))
        adb('shell','input','text',args.server)
        adb('shell','input','keyevent','KEYCODE_BACK')
        tap_label('Guardar y conectar')
        wait_library_ready()
        key('KEYCODE_BUTTON_L1');key('KEYCODE_BUTTON_L1')
    wait_for("Buscar en la biblioteca")
    key("KEYCODE_BUTTON_SELECT")
    time.sleep(2)
    adb("shell", "input", "text", args.game.replace(' ', '%s'))
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(1)
    key("KEYCODE_BUTTON_B")
    key("KEYCODE_DPAD_UP")
    key("KEYCODE_BUTTON_A")
    wait_for("Jugar en GameClub")
    key("KEYCODE_BUTTON_A")
    end=time.monotonic()+180
    while time.monotonic()<end:
        activity=adb('shell','dumpsys','activity','activities')
        if any('ResumedActivity' in line and 'NativeGameActivity' in line for line in activity.splitlines()):break
        time.sleep(1)
    else:raise RuntimeError('No se abrió la actividad nativa')
    time.sleep(12)
    screenshot=subprocess.run([args.adb,'-s',args.device,'exec-out','screencap','-p'],check=True,capture_output=True).stdout
    frame=Image.open(io.BytesIO(screenshot)).convert('RGB')
    center=frame.crop((frame.width//4,frame.height//4,frame.width*3//4,frame.height*3//4))
    assert len(center.getcolors(center.width*center.height) or [])>2,'El motor no mostró vídeo'
    print('OK: actividad MAME nativa con vídeo',flush=True)
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(.5)
    key('KEYCODE_DPAD_DOWN')
    key('KEYCODE_BUTTON_A')
    wait_for("GameClub · "+args.version)
    wait_library_ready()
    key("KEYCODE_BUTTON_R1")
    key("KEYCODE_BUTTON_R1")
    wait_for("Sincronizar motor con WebView",timeout=15)
    key("KEYCODE_BUTTON_L1")
    key("KEYCODE_BUTTON_L1")
    key("KEYCODE_BUTTON_SELECT")
    time.sleep(2)
    keyboard = adb("shell", "dumpsys", "input_method")
    assert any(flag in keyboard for flag in ("mInputShown=true", "mIsInputViewShown=true",
                                            "isInputViewShown=true")), "No aparece el teclado al volver"
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    print("APK release: jugar desde biblioteca, salir, LB/RB y Select/teclado correctos.", flush=True)


if __name__ == "__main__":
    main()
