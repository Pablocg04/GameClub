import io
import stat
import struct
import zipfile

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app
from app.pinball import inspect_package, rom_references


def table(script='Option Explicit'):
    """Contenedor OLE sintético de metadatos, no una mesa comercial ni una ROM."""
    free, end, fat = 0xffffffff, 0xfffffffe, 0xfffffffd
    header = bytearray(512)
    header[:8] = bytes.fromhex('d0cf11e0a1b11ae1')
    struct.pack_into('<HHHHH', header, 24, 0x3e, 3, 0xfffe, 9, 6)
    struct.pack_into('<IIIIIIIII', header, 40, 0, 1, 8, 0, 4096, end, 0, end, 0)
    struct.pack_into('<109I', header, 76, 9, *([free]*108))
    def directory(name, kind, child=free, start=end, size=0):
        raw = bytearray(128); encoded = (name+'\0').encode('utf-16le')
        raw[:len(encoded)] = encoded
        struct.pack_into('<HBBIII', raw, 64, len(encoded), kind, 1, free, free, child)
        struct.pack_into('<IQ', raw, 116, start, size)
        return raw
    entries = directory('Root Entry', 5, child=1)+directory('GameStg', 1, child=2)+directory('GameData', 2, start=0, size=4096)+bytes(128)
    code = script.encode('utf-8')
    data = (struct.pack('<I', 4)+b'CODE'+struct.pack('<I', len(code))+code).ljust(4096, b'\0')
    allocation = struct.pack('<128I', *list(range(1, 8)), end, end, fat, *([free]*118))
    return bytes(header)+data+entries+allocation


def rom():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as zipped: zipped.writestr('fictional-chip.u1', b'unit-test-data')
    return stream.getvalue()


def package(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as zipped:
        for name, data in files.items(): zipped.writestr(name, data)
    return stream.getvalue()


def test_table_package_normalizes_dependencies_and_detects_rom_revision(tmp_path):
    path = tmp_path/'Example.zip'
    path.write_bytes(package({'Folder/Example.vpx': table('Const cGameName = "test_113b"\nLoadVPM "1", "WPC.vbs", "0"'),
        'Folder/ROMS/TEST_113B.ZIP': rom(), 'Folder/Panel.directb2s': b'<DirectB2SData/>', 'Folder/Music/theme.ogg': b'music'}))
    info = inspect_package(path)
    assert info['table'] == 'Example.vpx'
    assert info['rom_candidates'] == ['test_113b'] and info['requires_rom']
    assert {item['destination'] for item in info['files']} == {'Example.vpx', 'pinmame/roms/test_113b.zip', 'Example.directb2s', 'music/theme.ogg'}


@pytest.mark.parametrize('rom_name', [None, 'wrong.zip'])
def test_missing_or_wrong_rom_is_rejected(tmp_path, rom_name):
    files = {'Example.vpx': table('Const cGameName="required"')}
    if rom_name: files[rom_name] = rom()
    path = tmp_path/'Example.zip'; path.write_bytes(package(files))
    with pytest.raises(HTTPException) as error: inspect_package(path)
    assert error.value.status_code == 422 and 'required.zip' in error.value.detail


@pytest.mark.parametrize('bad_name', ['../escape.vbs', 'C:/escape.vbs', 'CON.vbs', 'table./data.txt', 'installer.exe'])
def test_unsafe_package_paths_and_executables_are_rejected(tmp_path, bad_name):
    path = tmp_path/'Example.zip'
    path.write_bytes(package({'Example.vpx': table(), bad_name: b'file'}))
    with pytest.raises(HTTPException): inspect_package(path)


def test_script_comments_do_not_create_false_rom_dependencies():
    names, required = rom_references("'Const cGameName=\"wrong\"\nRem LoadVPM\nConst cGameName=\"actual\" 'old\n")
    assert names == ['actual'] and required
    assert rom_references("'Const cGameName=\"unused\"") == ([], False)


def test_ambiguous_tables_and_invalid_raw_table_are_rejected(tmp_path):
    path = tmp_path/'Example.zip'; path.write_bytes(package({'one.vpx': table(), 'two.vpx': table()}))
    with pytest.raises(HTTPException): inspect_package(path)
    path = tmp_path/'bad.vpx'; path.write_bytes(b'not-a-table')
    with pytest.raises(HTTPException): inspect_package(path)
    path.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1')+bytes(64))
    with pytest.raises(HTTPException): inspect_package(path)


def test_pinball_upload_manifest_and_mame_filter(tmp_path):
    app = create_app(tmp_path/'roms', tmp_path/'data', tmp_path/'media', token='token')
    raw = package({'Example.vpx': table('Const cGameName="required"'), 'required.zip': rom()})
    with TestClient(app, headers={'Authorization': 'Bearer token'}) as client:
        assert client.post('/api/systems/vpinball/upload', files={'file': ('Example.zip', raw)}).status_code == 201
        game = client.get('/api/games').json()[0]
        assert game['category'] == 'pinball'
        info = client.get(f'/api/games/{game["id"]}/pinball').json()
        assert info['roms'] == ['required'] and info['revision'] == game['revision']
        assert info['files'][0]['destination'] == 'Example.vpx'
        assert client.get(info['download_url']).content == raw
        assert client.get(f'/api/games/{game["id"]}/pinball', headers={'Authorization': ''}).status_code == 401
        assert client.post('/api/systems/vpinball/upload', files={'file': ('Example.zip', raw)}).status_code == 409
        bad = package({'Example.vpx': table('Const cGameName="missing"')})
        assert client.post('/api/systems/vpinball/upload', files={'file': ('Missing.zip', bad)}).status_code == 422
        assert len(client.get('/api/games').json()) == 1
        for name in ('pbaction.zip', 'pinbo.zip', 'speedbal.zip', 'arkanoid.zip'):
            assert client.post('/api/systems/mame/upload', files={'file': (name, package({'chip': b'data'}))}).status_code == 201
        pins = client.get('/api/games', params={'system_id': 'mame', 'category': 'pinball'}).json()
        assert {game['filename'] for game in pins} == {'pbaction.zip', 'pinbo.zip', 'speedbal.zip'}


def test_pinball_rom_zips_are_not_catalogued_as_tables(tmp_path):
    app = create_app(tmp_path/'roms', tmp_path/'data', tmp_path/'media', token='')
    folder = tmp_path/'roms/vpinball'; folder.mkdir()
    (folder/'required.zip').write_bytes(rom())
    (folder/'Example.vpx').write_bytes(table())
    with TestClient(app) as client:
        assert [game['filename'] for game in client.get('/api/games').json()] == ['Example.vpx']
