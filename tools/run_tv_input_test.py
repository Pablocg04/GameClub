"""Ejecuta la prueba Google TV e introduce eventos Android de mando mediante ADB."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flutter", required=True)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--device", default="emulator-5554")
    parser.add_argument("--target", default="integration_test/tv_player_test.dart")
    parser.add_argument("--game", default="sf2.zip")
    parser.add_argument("--core", default="mame2003_plus")
    parser.add_argument("--compare-timing", action="store_true")
    parser.add_argument("--flavor", choices=("mobile","tv"), default="tv")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    root = Path(__file__).resolve().parents[1]

    def key(name):
        subprocess.run([args.adb, "-s", args.device, "shell", "input", "gamepad", "keyevent", name], check=True)

    process = subprocess.Popen([args.flutter, "drive", "--driver=integration_test/tv_driver.dart",
                                "--target=" + args.target, "--flavor", args.flavor, "--dart-define=TV_TEST_GAME=" + args.game,
                                "--dart-define=TV_TEST_CORE=" + args.core,
                                "--dart-define=TV_COMPARE_TIMING=" + str(args.compare_timing).lower(),
                                "-d", args.device, "--no-dds"],
                               cwd=root / "client", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", env=os.environ.copy())
    sent = set()
    for line in process.stdout:
        print(line, end="", flush=True)
        for marker in ("TV_INPUT_READY", "TV_BUTTON_A_READY", "TV_MENU_READY", "TV_RESUME_READY", "TV_EXIT_READY", "TV_CONFIRM_EXIT_READY",
                       "TV_LIBRARY_RB_READY", "TV_LIBRARY_LB_READY", "TV_SEARCH_READY", "TV_SEARCH_TEXT_READY"):
            if marker in line and marker not in sent:
                sent.add(marker)
                if marker == "TV_BUTTON_A_READY":
                    subprocess.Popen([args.adb,"-s",args.device,"shell","input","gamepad","keyevent","--duration","3000","KEYCODE_BUTTON_A"])
                elif marker == "TV_CONFIRM_EXIT_READY":
                    key("KEYCODE_DPAD_DOWN")
                    key("KEYCODE_BUTTON_A")
                elif marker == "TV_INPUT_READY":
                    subprocess.run([args.adb, "-s", args.device, "shell", "input", "joystick", "motionevent", "MOVE", "0.8", "0.0"], check=True)
                    time.sleep(.25)
                    subprocess.run([args.adb, "-s", args.device, "shell", "input", "joystick", "motionevent", "MOVE", "0.0", "0.0"], check=True)
                    key("KEYCODE_BUTTON_SELECT")
                    key("KEYCODE_BUTTON_START")
                elif marker == "TV_MENU_READY":
                    held = subprocess.Popen([args.adb, "-s", args.device, "shell", "input", "gamepad", "keyevent", "--longpress", "KEYCODE_BUTTON_SELECT"])
                    time.sleep(.15)
                    key("KEYCODE_BUTTON_START")
                    held.wait()
                elif marker == "TV_RESUME_READY":
                    key("KEYCODE_BUTTON_A")
                elif marker == "TV_LIBRARY_RB_READY":
                    key("KEYCODE_BUTTON_R1")
                elif marker == "TV_LIBRARY_LB_READY":
                    key("KEYCODE_BUTTON_L1")
                elif marker == "TV_SEARCH_READY":
                    key("KEYCODE_BUTTON_SELECT")
                elif marker == "TV_SEARCH_TEXT_READY":
                    time.sleep(2)
                    keyboard = subprocess.run([args.adb, "-s", args.device, "shell", "dumpsys", "input_method"],
                                              capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout
                    if not any(flag in keyboard for flag in ("mInputShown=true", "isInputViewShown=true", "mIsInputViewShown=true")):
                        process.terminate()
                        raise RuntimeError("El teclado Android no está visible tras Select")
                    subprocess.run([args.adb, "-s", args.device, "shell", "input", "text", "sf2"], check=True)
                else:
                    subprocess.run([args.adb, "-s", args.device, "shell", "input", "keyevent", "KEYCODE_BACK"], check=True)
    sys.exit(process.wait())


if __name__ == "__main__":
    main()
