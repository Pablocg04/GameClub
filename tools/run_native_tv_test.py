"""Prueba la actividad nativa con vídeo y eventos de mando/táctiles reales de Android."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import json
import io
from PIL import Image


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--flutter",required=True)
    parser.add_argument("--adb",required=True)
    parser.add_argument("--device",default="emulator-5554")
    parser.add_argument("--game",default="arkanoid.zip")
    parser.add_argument("--system",choices=("mame","nes","atari2600"),default="mame")
    parser.add_argument("--touch",action="store_true")
    parser.add_argument("--flavor",choices=("mobile","tv"),default="tv")
    parser.add_argument("--orientation",choices=("auto","portrait","landscape"),default="auto")
    parser.add_argument("--rotate",action="store_true")
    parser.add_argument("--server",default="http://192.168.0.47:8001")
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8",errors="replace")
    def adb(*arguments):subprocess.run([args.adb,"-s",args.device,*arguments],check=True)
    # El aviso inicial de pantalla completa del sistema detiene SDL al robarle el foco.
    if args.device.startswith('emulator-'):
        adb('shell','settings','put','secure','immersive_mode_confirmations','confirmed')
    def key(name):adb("shell","input","gamepad","keyevent","--duration","100",name);time.sleep(.2)
    process=subprocess.Popen([args.flutter,"drive","--driver=integration_test/tv_driver.dart","--target=integration_test/native_arcade_test.dart",
        "--flavor",args.flavor,"--dart-define=NATIVE_TEST_VARIANT="+args.flavor,
        "--dart-define=NATIVE_TEST_SERVER="+args.server,
        "--dart-define=NATIVE_TEST_ORIENTATION="+args.orientation,"--dart-define=NATIVE_TEST_ROTATE="+str(args.rotate).lower(),
        "--dart-define=NATIVE_TEST_GAME="+args.game,"--dart-define=NATIVE_TEST_SYSTEM="+args.system,"--dart-define=NATIVE_TEST_TOUCH="+str(args.touch).lower(),"-d",args.device,"--no-dds"],
        cwd=Path(__file__).resolve().parents[1]/"client",stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",env=os.environ.copy())
    sent=set()
    controls=None
    for line in process.stdout:
        print(line,end="",flush=True)
        capture_marker=next((marker for marker in ("NATIVE_CAPTURE_READY ","NATIVE_ROTATED_CAPTURE_READY ") if marker in line),None)
        if capture_marker:
            remote=line.split(capture_marker,1)[1].strip()
            raw=subprocess.run([args.adb,"-s",args.device,"exec-out","run-as","com.gameclub.gameclub","cat",remote[:-4]+".layout"],capture_output=True,check=True).stdout
            controls=json.loads(raw)
            data=subprocess.run([args.adb,"-s",args.device,"exec-out","run-as","com.gameclub.gameclub","cat",remote],capture_output=True,check=True).stdout
            if data.startswith(b"BM"):
                destination=Path(os.environ["TEMP"])/"opencode"/("native-"+args.flavor+"-"+args.orientation+"-"+("rotated-" if "ROTATED" in capture_marker else "")+args.game+".png")
                Image.open(io.BytesIO(data)).save(destination)
                print("Captura nativa:",destination,flush=True)
        for marker in ("NATIVE_PREPARE_PORTRAIT_READY","NATIVE_INPUT_READY","NATIVE_AXIS_READY","NATIVE_ROTATE_READY","NATIVE_MENU_READY","NATIVE_RESUME_READY","NATIVE_EXIT_READY","NATIVE_CONFIRM_EXIT_READY","NATIVE_SECOND_EXIT_READY","NATIVE_SECOND_CONFIRM_EXIT_READY"):
            if marker not in line or marker in sent:continue
            sent.add(marker)
            if marker=="NATIVE_PREPARE_PORTRAIT_READY":
                adb("shell","wm","user-rotation","lock","0")
            elif marker=="NATIVE_INPUT_READY":
                if args.touch:
                    assert controls is not None
                    screen=Image.open(io.BytesIO(subprocess.run([args.adb,"-s",args.device,"exec-out","screencap","-p"],capture_output=True,check=True).stdout))
                    factor=min(screen.width/controls['width'],screen.height/controls['height'])
                    offset_x=(screen.width-controls['width']*factor)/2;offset_y=(screen.height-controls['height']*factor)/2
                    for index in ((2,3,8) if args.system=="mame" else (3,3,3,8)):
                        button=next(button for button in controls['buttons'] if button['index']==index)
                        x=round(offset_x+button['x']*factor);y=round(offset_y+button['y']*factor)
                        adb("shell","input","touchscreen","swipe",str(x),str(y),str(x),str(y),"250")
                        if args.system!="mame" and index==3:time.sleep(1)
                else:
                    if args.system=="mame": key("KEYCODE_BUTTON_SELECT")
                    else:
                        key("KEYCODE_BUTTON_START");time.sleep(1);key("KEYCODE_BUTTON_START");time.sleep(1)
                    key("KEYCODE_BUTTON_START");key("KEYCODE_DPAD_RIGHT");key("KEYCODE_BUTTON_A")
            elif marker=="NATIVE_AXIS_READY":
                adb("shell","input","joystick","motionevent","MOVE","0.8","0.0")
                time.sleep(.4)
                adb("shell","input","joystick","motionevent","MOVE","0.0","0.0")
            elif marker=="NATIVE_ROTATE_READY":
                adb("shell","wm","user-rotation","lock","1")
            elif marker=="NATIVE_MENU_READY":
                held=subprocess.Popen([args.adb,"-s",args.device,"shell","input","gamepad","keyevent","--longpress","KEYCODE_BUTTON_SELECT"])
                time.sleep(.15);key("KEYCODE_BUTTON_START");held.wait()
            elif marker=="NATIVE_RESUME_READY":
                key("KEYCODE_DPAD_DOWN");key("KEYCODE_DPAD_UP");key("KEYCODE_BUTTON_A")
            elif marker in ("NATIVE_CONFIRM_EXIT_READY","NATIVE_SECOND_CONFIRM_EXIT_READY"):
                key("KEYCODE_DPAD_DOWN");key("KEYCODE_BUTTON_A")
            else:
                adb("shell","input","keyevent","KEYCODE_BACK")
    sys.exit(process.wait())


if __name__=="__main__":main()
