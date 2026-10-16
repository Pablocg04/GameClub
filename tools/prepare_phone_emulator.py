"""Crea un AVD móvil aislado usando una imagen Android ya instalada en el SDK."""
import argparse
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('root',type=Path)
parser.add_argument('--image',type=Path,required=True)
args=parser.parse_args()
root=args.root.resolve();image=args.image.resolve()
assert root.parent.is_dir() and (image/'system.img').is_file()
avds=root/'avds';avd=avds/'GameClubPhone.avd'
avd.mkdir(parents=True,exist_ok=True)
(avds/'GameClubPhone.ini').write_text(f'avd.ini.encoding=UTF-8\npath={avd}\ntarget=android-36\n',encoding='utf-8')
config={'avd.ini.encoding':'UTF-8','AvdId':'GameClubPhone','avd.ini.displayname':'GameClub Phone Test',
 'abi.type':'x86_64','hw.cpu.arch':'x86_64','hw.cpu.ncore':'2','image.sysdir.1':str(image)+'\\',
 'tag.id':'google_apis_playstore','tag.display':'Google Play','hw.device.name':'pixel_6',
 'hw.ramSize':'2048','hw.lcd.width':'1080','hw.lcd.height':'2400','hw.lcd.density':'420',
 'hw.initialOrientation':'portrait','hw.dPad':'no','hw.keyboard':'yes','hw.mainKeys':'no',
 'hw.gpu.enabled':'yes','hw.gpu.mode':'swiftshader_indirect','disk.dataPartition.size':'4G',
 'showDeviceFrame':'no','fastboot.forceColdBoot':'yes','PlayStore.enabled':'true','hw.audioInput':'no',
 'hw.sensors.orientation':'yes','hw.sensors.proximity':'no'}
(avd/'config.ini').write_text(''.join(f'{key}={value}\n' for key,value in config.items()),encoding='utf-8')
print(f'AVD móvil listo. ANDROID_AVD_HOME={avds}')
