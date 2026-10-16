"""Verifica que los APK móvil y TV tienen identidad compatible y lanzadores distintos."""
import argparse
from pathlib import Path
import re
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--aapt',required=True)
parser.add_argument('--directory',type=Path,required=True)
args=parser.parse_args()
version,code=re.search(r'^version:\s*([^+\s]+)\+(\d+)',(Path(__file__).resolve().parents[1]/'client/pubspec.yaml').read_text(encoding='utf-8'),re.M).groups()
packages=[]
for variant,label,leanback in [('mobile','GameClub',False),('tv','GameClub TV',True)]:
    apk=args.directory/f'app-{variant}-release.apk'
    data=subprocess.run([args.aapt,'dump','badging',str(apk)],capture_output=True,check=True,encoding='utf-8',errors='replace').stdout
    package=re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'",data).groups()
    assert package==('com.gameclub.gameclub',code,version),package
    assert f"application-label:'{label}'" in data
    assert ('leanback-launchable-activity:' in data)==leanback
    assert ('uses-feature: name=\'android.software.leanback\'' in data)==leanback
    assert "sdkVersion:'24'" in data
    assert "native-code: 'arm64-v8a' 'armeabi-v7a' 'x86_64'" in data
    packages.append(package)
    print(f'{variant}: {label}, versión {package[2]}, código {package[1]}, Leanback={leanback}')
assert packages[0]==packages[1]
print('Los dos APK actualizan el paquete anterior conservando sus datos.')
