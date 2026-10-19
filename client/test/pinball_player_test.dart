import 'dart:convert';
import 'dart:io';
import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/pinball_player.dart';
import 'package:path/path.dart' as p;

void main() {
  test('prepara la mesa y las ROMs sin sobrescribir el NVRAM existente',
      () async {
    final root = await Directory.systemTemp.createTemp('gameclub-pinball-');
    addTearDown(() => root.delete(recursive: true));
    final archive = Archive()
      ..addFile(ArchiveFile('Folder/Table.vpx', 4, [1, 2, 3, 4]))
      ..addFile(ArchiveFile('ROM.zip', 3, [4, 5, 6]))
      ..addFile(ArchiveFile('state.nv', 2, [0, 0]));
    final package = File(p.join(root.path, 'source.zip'));
    await package.writeAsBytes(ZipEncoder().encode(archive));
    final decoded = ZipDecoder().decodeBytes(await package.readAsBytes());
    final files = Directory(p.join(root.path, 'table'));
    final nv = PinballPlayer.safeFile(files, 'pinmame/nvram/game.nv');
    await nv.parent.create(recursive: true);
    await nv.writeAsBytes([9, 9]);
    final names = {
      'Folder/Table.vpx': 'Table.vpx',
      'ROM.zip': 'pinmame/roms/rom.zip',
      'state.nv': 'pinmame/nvram/game.nv'
    };
    final manifest = {
      'table': 'Table.vpx',
      'files': [
        for (final item in decoded.files)
          {
            'member': item.name,
            'destination': names[item.name],
            'size': item.size,
            'crc': item.crc32!.toRadixString(16).padLeft(8, '0')
          }
      ]
    };
    final result = PinballPlayer.extractPackage(
        [package.path, files.path, jsonEncode(manifest)]);
    expect(await File(result).readAsBytes(), [1, 2, 3, 4]);
    expect(
        await PinballPlayer.safeFile(files, 'pinmame/roms/rom.zip')
            .readAsBytes(),
        [4, 5, 6]);
    expect(await nv.readAsBytes(), [9, 9]);
  });

  test('rechaza destinos fuera de la carpeta y un manifiesto cambiado',
      () async {
    final root = await Directory.systemTemp.createTemp('gameclub-pinball-');
    addTearDown(() => root.delete(recursive: true));
    expect(() => PinballPlayer.safeFile(root, '../outside'), throwsException);
    expect(() => PinballPlayer.safeFile(root, 'C:/outside'), throwsException);
    final archive = Archive()..addFile(ArchiveFile('Table.vpx', 2, [1, 2]));
    final source = File(p.join(root.path, 'source.zip'));
    await source.writeAsBytes(ZipEncoder().encode(archive));
    final manifest = {
      'table': 'Table.vpx',
      'files': [
        {
          'member': 'Table.vpx',
          'destination': 'Table.vpx',
          'size': 99,
          'crc': '00000000'
        }
      ]
    };
    expect(
        () => PinballPlayer.extractPackage(
            [source.path, p.join(root.path, 'table'), jsonEncode(manifest)]),
        throwsException);
  });

  test('exporta VPXZ con mesa y dependencias, sin incluir el archivo exportado',
      () async {
    final root = await Directory.systemTemp.createTemp('gameclub-vpxz-');
    addTearDown(() => root.delete(recursive: true));
    final folder = Directory(p.join(root.path, 'table'));
    await folder.create();
    await File(p.join(folder.path, 'Table.vpx')).writeAsBytes([1, 2, 3]);
    final result = await PinballPlayer.exportAndroid(
        [folder.path, p.join(root.path, 'share', 'table.vpxz')]);
    final archive = ZipDecoder().decodeBytes(await File(result).readAsBytes());
    expect(archive.files.where((file) => file.isFile).map((file) => file.name),
        ['Table.vpx']);
  });
}
