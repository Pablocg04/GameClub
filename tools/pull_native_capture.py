import argparse
from pathlib import Path
import subprocess
import io
from PIL import Image

parser=argparse.ArgumentParser()
parser.add_argument('--adb',required=True)
parser.add_argument('--device',default='emulator-5554')
parser.add_argument('source')
parser.add_argument('destination',type=Path)
args=parser.parse_args()
assert args.destination.parent.is_dir()
data=subprocess.run([args.adb,'-s',args.device,'exec-out','run-as','com.gameclub.gameclub','cat',args.source],capture_output=True,check=True).stdout
if not data.startswith(b'BM'):
    raise RuntimeError(f'Captura no válida: {len(data)} bytes, cabecera {data[:120]!r}')
image=Image.open(io.BytesIO(data))
image.save(args.destination)
print(image.size, args.destination)
