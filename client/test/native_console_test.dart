import 'dart:io';
import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:archive/archive.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/native_console.dart';
import 'package:gameclub/game_files.dart';
import 'package:path/path.dart' as p;

class ConsoleAdapter implements HttpClientAdapter {
  List<int> bytes = [1, 2, 3, 4];
  int downloads = 0;
  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? stream,
      Future<void>? cancel) async {
    downloads++;
    return ResponseBody.fromBytes(bytes, 200, headers: {
      Headers.contentLengthHeader: ['${bytes.length}']
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('reemplazar una ROM por otra del mismo tamaño invalida la caché',
      () async {
    final root = await Directory.systemTemp.createTemp('gameclub-cache-');
    addTearDown(() => root.delete(recursive: true));
    final adapter = ConsoleAdapter();
    final api = GameClubApi('http://fixture', '')
      ..dio.httpClientAdapter = adapter;
    final console = NativeConsole(api);
    final game = <String, dynamic>{
      'id': 'game',
      'filename': 'game.nes',
      'system_id': 'nes',
      'size': 4,
      'revision': '1'
    };
    final first = await console.prepare(game, root);
    expect(await first.readAsBytes(), [1, 2, 3, 4]);
    adapter.bytes = [4, 3, 2, 1];
    final replacement = await console.prepare({...game, 'revision': '2'}, root);
    expect(await replacement.readAsBytes(), [4, 3, 2, 1]);
    await console.prepare({...game, 'revision': '2'}, root);
    expect(adapter.downloads, 2);
  });

  test('dos servidores con el mismo juego no comparten la descarga', () async {
    final root = await Directory.systemTemp.createTemp('gameclub-libraries-');
    addTearDown(() => root.delete(recursive: true));
    final firstAdapter = ConsoleAdapter();
    final secondAdapter = ConsoleAdapter()..bytes = [9, 8, 7, 6];
    final first = GameClubApi('http://library-one', '')
      ..dio.httpClientAdapter = firstAdapter;
    final second = GameClubApi('http://library-two', '')
      ..dio.httpClientAdapter = secondAdapter;
    final game = <String, dynamic>{
      'id': 'same-id',
      'filename': 'same.nes',
      'size': 4,
      'revision': '1'
    };
    final one = await GameFiles.fetch(
        first, game, GameFiles.location(first, game, root));
    final two = await GameFiles.fetch(
        second, game, GameFiles.location(second, game, root));
    expect(one.path, isNot(two.path));
    expect(await one.readAsBytes(), [1, 2, 3, 4]);
    expect(await two.readAsBytes(), [9, 8, 7, 6]);
  });

  test('el ZIP Atari usa la ROM y no el estado, sin extraer rutas externas',
      () async {
    final root = await Directory.systemTemp.createTemp('gameclub-console-');
    addTearDown(() => root.delete(recursive: true));
    final archive = Archive()
      ..addFile(ArchiveFile('../outside.bin', 4, [1, 2, 3, 4]))
      ..addFile(ArchiveFile('game.0a.sta', 2, [7, 8]));
    final zipped = File('${root.path}/game.zip');
    await zipped.writeAsBytes(ZipEncoder().encode(archive));
    final result = await NativeConsole.unpack(
        'atari2600', zipped, Directory('${root.path}/output'));
    expect(p.normalize(result.path), p.join(root.path, 'output', 'game.bin'));
    expect(await result.readAsBytes(), [1, 2, 3, 4]);
    expect(await File('${root.path}/outside.bin').exists(), false);
  });

  test('rechaza estados y ZIPs ambiguos y admite extensiones NES en mayúsculas',
      () async {
    final root = await Directory.systemTemp.createTemp('gameclub-console-');
    addTearDown(() => root.delete(recursive: true));
    final output = Directory('${root.path}/output');
    final sta = File('${root.path}/game.sta');
    await sta.writeAsBytes([1, 2]);
    await expectLater(
        NativeConsole.unpack('atari2600', sta, output), throwsException);
    for (final names in [
      ['game.sta'],
      ['first.nes', 'second.NES']
    ]) {
      final archive = Archive();
      for (final name in names) {
        archive.addFile(ArchiveFile(name, 2, [1, 2]));
      }
      final zipped = File('${root.path}/game.zip');
      await zipped.writeAsBytes(ZipEncoder().encode(archive));
      await expectLater(
          NativeConsole.unpack('nes', zipped, output), throwsException);
    }
    final nes = File('${root.path}/game.NES');
    await nes.writeAsBytes([1, 2]);
    expect(await NativeConsole.unpack('nes', nes, output), nes);
  });

  test('motores incluidos verifican sus huellas, reparan caché y no piden API',
      () async {
    final root = await Directory.systemTemp.createTemp('gameclub-core-');
    addTearDown(() => root.delete(recursive: true));
    final console = NativeConsole(GameClubApi('http://127.0.0.1:1', ''));
    final registry = jsonDecode(
        await rootBundle.loadString('assets/native_console_cores.json')) as Map;
    for (final core in ['nestopia', 'stella']) {
      final binary =
          await console.core('windows-x86_64', core, root, bundled: true);
      expect(await binary.length(),
          registry['platforms']['windows-x86_64'][core]['binary_size']);
      await binary.writeAsBytes([0]);
      final repaired =
          await console.core('windows-x86_64', core, root, bundled: true);
      expect(await repaired.length(),
          registry['platforms']['windows-x86_64'][core]['binary_size']);
    }
  });
}
