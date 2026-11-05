"""Entrega el NRO comprobado y su documentación, sin datos ni ROMs."""
import hashlib
import json
from pathlib import Path
import re
import shutil
from build_switch import verify

root=Path(__file__).resolve().parents[1]
version=re.search(r'^version:\s*([^+\s]+)',(root/'client/pubspec.yaml').read_text(),re.M).group(1)
build=root/'switch-client/build'
report=verify(build/'GameClub.nro',build/'GameClub.elf',version)
saved=json.loads((build/'verification.json').read_text())
assert saved==report, 'La comprobación no corresponde al NRO actual'
target=root/'dist'/('switch-'+version)
target.mkdir(parents=True,exist_ok=True)
dest=target/'GameClub-Switch.nro'
shutil.copy2(build/'GameClub.nro',dest)
assert hashlib.sha256(dest.read_bytes()).hexdigest()==report['sha256']
shutil.copy2(root/'SWITCH.md',target/'SWITCH.md')
shutil.copy2(root/'THIRD_PARTY_NOTICES.md',target/'THIRD_PARTY_NOTICES.md')
(target/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(dest)
