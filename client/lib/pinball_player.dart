import 'dart:convert';
import 'dart:io';
import 'package:archive/archive_io.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:window_manager/window_manager.dart';
import 'api.dart';
import 'game_files.dart';
import 'native_runtime.dart';
import 'television.dart';

class PinballPlayer {
  PinballPlayer(this.api,
      {this.onProgress, this.onStarted, this.onHostStarted});
  final GameClubApi api;
  final void Function(String, double?)? onProgress;
  final void Function(int)? onStarted;
  final void Function(int)? onHostStarted;

  static File safeFile(Directory root, String relative) {
    if (relative.startsWith('/') ||
        relative.contains('\\') ||
        relative.contains(':') ||
        relative.split('/').any((part) => {'', '.', '..'}.contains(part))) {
      throw Exception('Ruta de paquete pinball inválida');
    }
    return File(p.joinAll([root.path, ...relative.split('/')]));
  }

  static bool mutable(String name) =>
      name.toLowerCase().endsWith('.ini') ||
      ['pinmame/nvram/', 'pinmame/cfg/', 'user/', 'cache/']
          .any(name.toLowerCase().startsWith);

  static String extractPackage(List<String> arguments) {
    final source = File(arguments[0]), root = Directory(arguments[1]);
    final manifest = jsonDecode(arguments[2]) as Map;
    root.createSync(recursive: true);
    if (manifest['raw_table'] == true) {
      final destination = safeFile(root, manifest['table'] as String);
      source.copySync(destination.path);
    } else {
      final input = InputFileStream(source.path);
      try {
        final archive = ZipDecoder().decodeStream(input, verify: true);
        for (final raw in manifest['files'] as List) {
          final item = raw as Map;
          final member = archive.find(item['member'] as String);
          if (member == null ||
              !member.isFile ||
              member.isSymbolicLink ||
              member.size != item['size'] ||
              member.crc32 == null ||
              member.crc32!.toRadixString(16).padLeft(8, '0') != item['crc']) {
            throw Exception(
                'El paquete no coincide con el manifiesto. Vuelve a escanear la biblioteca.');
          }
          final destination = safeFile(root, item['destination'] as String);
          if (mutable(item['destination'] as String) &&
              destination.existsSync()) {
            continue;
          }
          destination.parent.createSync(recursive: true);
          final output = OutputFileStream('${destination.path}.part');
          try {
            member.writeContent(output);
          } finally {
            output.closeSync();
          }
          final temporary = File('${destination.path}.part');
          if (destination.existsSync()) destination.deleteSync();
          temporary.renameSync(destination.path);
        }
      } finally {
        input.closeSync();
      }
    }
    return safeFile(root, manifest['table'] as String).path;
  }

  Future<Json> prepare(Json game, Directory directory) async {
    final manifest = (await api.dio.get<Json>(
            '/api/games/${game['id']}/pinball',
            options: Options(receiveTimeout: const Duration(minutes: 5))))
        .data!;
    final extension = p.extension(game['filename'] as String).toLowerCase();
    final source = File(p.join(directory.path, 'package$extension'));
    await GameFiles.fetch(
        api,
        {...game, 'revision': manifest['revision'], 'size': manifest['size']},
        source,
        onProgress: (read, total) => onProgress?.call(
            'Preparando paquete de pinball', total > 0 ? read / total : null));
    final files = Directory(p.join(directory.path, 'table'));
    final ready = File(p.join(directory.path, '.prepared.json'));
    Json previous = {};
    if (await ready.exists()) {
      try {
        final decoded = jsonDecode(await ready.readAsString());
        if (decoded is Map) previous = Json.from(decoded);
      } on FormatException {
        previous = {};
      }
    }
    final assets = manifest['raw_table'] == true
        ? [
            {'destination': manifest['table'], 'size': manifest['size']}
          ]
        : (manifest['files'] as List).cast<Map>();
    var intact = previous['signature'] == manifest['signature'];
    if (intact) {
      for (final item in assets) {
        final file = safeFile(files, item['destination'] as String);
        if (!await file.exists() ||
            !mutable(item['destination'] as String) &&
                await file.length() != item['size']) {
          intact = false;
          break;
        }
      }
    }
    if (intact) {
      return {
        ...manifest,
        'primary': safeFile(files, manifest['table'] as String).path,
        'directory': files.path
      };
    }
    final destinations = assets.map((item) => item['destination']).toSet();
    for (final old in previous['files'] as List? ?? []) {
      final name = old as String;
      if (!destinations.contains(name) && !mutable(name)) {
        final stale = safeFile(files, name);
        if (await stale.exists()) await stale.delete();
      }
    }
    onProgress?.call('Preparando mesa, ROMs y panel…', null);
    final primary = await compute(
        extractPackage, [source.path, files.path, jsonEncode(manifest)]);
    await ready.writeAsString(
        jsonEncode({
          'signature': manifest['signature'],
          'files': destinations.toList()
        }),
        flush: true);
    return {...manifest, 'primary': primary, 'directory': files.path};
  }

  static Future<String> extractRuntime(List<String> arguments) async {
    final archivePath = arguments[0], root = Directory(arguments[1]);
    final metadata = jsonDecode(arguments[2]) as Map;
    final expected = metadata['files'] as Map;
    final input = InputFileStream(archivePath);
    root.createSync(recursive: true);
    try {
      final archive = ZipDecoder().decodeStream(input, verify: true);
      for (final item in expected.entries) {
        final member = archive.find(item.key as String);
        if (member == null ||
            member.isSymbolicLink ||
            member.size != (item.value as Map)['size']) {
          throw Exception('Motor VPX incompleto');
        }
        final destination = safeFile(root, item.key as String);
        if (await destination.exists() &&
            await NativeRuntime.fileHash(destination) == item.value['sha256']) {
          continue;
        }
        destination.parent.createSync(recursive: true);
        final output = OutputFileStream('${destination.path}.part');
        try {
          member.writeContent(output);
        } finally {
          output.closeSync();
        }
        final temporary = File('${destination.path}.part');
        if (await NativeRuntime.fileHash(temporary) != item.value['sha256']) {
          temporary.deleteSync();
          throw Exception('La huella de un archivo VPX no coincide');
        }
        if (destination.existsSync()) destination.deleteSync();
        temporary.renameSync(destination.path);
      }
    } finally {
      input.closeSync();
    }
    return safeFile(root, metadata['binary'] as String).path;
  }

  Future<File> runtime(Directory support) async {
    final registry = (await api.dio.get<Json>('/api/player/pinball')).data!;
    final entry =
        Json.from((registry['platforms'] as Map)['windows-x86_64'] as Map);
    final folder = Directory(
        p.join(support.path, 'runtime', registry['version'] as String));
    await folder.create(recursive: true);
    final archive = File(p.join(folder.path, 'vpx.zip'));
    if (!await archive.exists() ||
        await archive.length() != entry['size'] ||
        await NativeRuntime.fileHash(archive) != entry['sha256']) {
      final temporary = File('${archive.path}.part');
      try {
        await api.dio.download(
            '/api/player/pinball/windows-x86_64', temporary.path,
            options: Options(receiveTimeout: const Duration(minutes: 10)),
            onReceiveProgress: (read, total) => onProgress?.call(
                'Descargando Visual Pinball X',
                total > 0 ? read / total : null));
        if (await temporary.length() != entry['size'] ||
            await NativeRuntime.fileHash(temporary) != entry['sha256']) {
          throw Exception(
              'La descarga de VPX no coincide con su huella fijada');
        }
        if (await archive.exists()) await archive.delete();
        await temporary.rename(archive.path);
      } finally {
        if (await temporary.exists()) await temporary.delete();
      }
    }
    onProgress?.call('Verificando el motor Visual Pinball…', null);
    return File(await compute(extractRuntime,
        [archive.path, p.join(folder.path, 'player'), jsonEncode(entry)]));
  }

  static const defaultIni = '''[Player]
PlayfieldFullScreen=1
[Plugin.PinMAME]
Enable=1
[Plugin.ScoreView]
Enable=1
[ScoreView]
ScoreViewOutput=2
ScoreViewWidth=320
ScoreViewHeight=120
ScoreViewWndX=16
ScoreViewWndY=16
''';

  /// The host supplies a consistent pad mapping. Keep video/audio and saved data,
  /// but restore the keyboard actions it uses instead of VPX's old pad layout.
  static String configureControls(String source) {
    final pending = <String, String>{
      'Mapping.LeftFlipper': 'Key;225',
      'Mapping.RightFlipper': 'Key;229',
      'Mapping.LeftStagedFlipper': 'Key;225',
      'Mapping.RightStagedFlipper': 'Key;229',
      'Mapping.Credit1': 'Key;34',
      'Mapping.Start': 'Key;30',
      'Mapping.LaunchBall': 'Key;40',
      'Mapping.LeftNudge': 'Key;29',
      'Mapping.RightNudge': 'Key;56',
      'Mapping.CenterNudge': 'Key;44',
    };
    final output = <String>[];
    var inInput = false, found = false;
    void remaining() {
      output
          .addAll(pending.entries.map((item) => '${item.key} = ${item.value}'));
      pending.clear();
    }

    for (final line in const LineSplitter().convert(source)) {
      if (line.trim().startsWith('[')) {
        if (inInput) remaining();
        inInput = line.trim().toLowerCase() == '[input]';
        found |= inInput;
      }
      final key = line.split('=').first.trim();
      if (inInput && pending.containsKey(key)) {
        output.add('$key = ${pending.remove(key)}');
      } else {
        output.add(line);
      }
    }
    if (!found) output.add('[Input]');
    remaining();
    return '${output.join('\n')}\n';
  }

  static Future<String> exportAndroid(List<String> arguments) async {
    final folder = Directory(arguments[0]), destination = arguments[1];
    await File(destination).parent.create(recursive: true);
    final encoder = ZipFileEncoder();
    await encoder.zipDirectory(folder,
        filename: destination, followLinks: false);
    return destination;
  }

  Future<void> play(Json game) async {
    if (!Platform.isWindows && !Platform.isAndroid) {
      throw Exception(
          'Visual Pinball está preparado para PC Windows y Android compatible');
    }
    if (Platform.isAndroid) {
      final capabilities = await DevicePlatform.channel
              .invokeMapMethod<String, dynamic>('pinballCapabilities') ??
          {};
      if (capabilities['compatible'] != true) {
        throw Exception(capabilities['reason'] ??
            'VPX necesita Android 13 o posterior y ARM64');
      }
    }
    final documents = await getApplicationDocumentsDirectory();
    final prepared = await prepare(
        game,
        Directory(p.join(documents.path, 'GameClub', 'pinball',
            GameFiles.libraryKey(api), game['id'] as String)));
    final support = Directory(
        p.join((await getApplicationSupportDirectory()).path, 'pinball'));
    final preferences = Directory(p.join(support.path, 'saves',
        GameFiles.libraryKey(api), game['id'] as String));
    await preferences.create(recursive: true);
    if (Platform.isAndroid) {
      onProgress?.call('Abriendo pinball integrado en GameClub…', null);
      try {
        await DevicePlatform.channel.invokeMethod<void>('playPinball', {
          'path': prepared['primary'],
          'preferences': preferences.path,
          'title': game['title'],
          'roms': prepared['rom_candidates'] ?? [],
          'requiresRom': prepared['requires_rom'] == true,
          'orientation': DevicePlatform.mobileOrientation,
          'touchScale': DevicePlatform.touchScale,
        });
      } on PlatformException catch (error) {
        throw Exception(
            error.message ?? 'El motor pinball no pudo terminar la partida');
      }
      return;
    }
    final engine = await runtime(support);
    final ini = File(p.join(preferences.path, 'VPinballX.ini'));
    await ini.writeAsString(
        configureControls(
            await ini.exists() ? await ini.readAsString() : defaultIni),
        flush: true);
    final host = File(
        p.join(p.dirname(Platform.resolvedExecutable), 'gameclub_native.exe'));
    if (!await host.exists()) {
      throw Exception(
          'Falta gameclub_native.exe. Extrae el paquete completo de GameClub.');
    }
    var initialize = false;
    for (final name
        in (prepared['rom_candidates'] as List? ?? []).cast<String>()) {
      if (name.startsWith('afm_') &&
          (!await File(p.join(preferences.path, '.initialized-afm-v2'))
                  .exists() ||
              !await safeFile(Directory(prepared['directory'] as String),
                      'pinmame/nvram/$name.nv')
                  .exists())) {
        initialize = true;
      }
    }
    final log = File(p.join(preferences.path, 'player.log')).openWrite();
    try {
      final process = await Process.start(
          host.path,
          [
            '--pinball',
            engine.path,
            prepared['primary'] as String,
            preferences.path,
            if (initialize) '--initialize',
            if (prepared['requires_rom'] == true) '--warmup=15000',
          ],
          workingDirectory: engine.parent.path);
      onHostStarted?.call(process.pid);
      await process.stdin.close();
      final stdout = process.stdout
          .transform(const Utf8Decoder(allowMalformed: true))
          .transform(const LineSplitter())
          .forEach((line) {
        log.writeln(line);
        const prefix = 'GAMECLUB_PINBALL_ENGINE ';
        if (line.startsWith(prefix)) {
          final pid = int.tryParse(line.substring(prefix.length).trim());
          if (pid != null) onStarted?.call(pid);
        }
        if (line == 'GAMECLUB_PINBALL_STATE initializing') {
          onProgress?.call(
              'Inicializando la ROM por primera vez. La mesa se volverá a abrir automáticamente…',
              null);
        }
        if (line == 'GAMECLUB_PINBALL_STATE menu') {
          onProgress?.call(
              'Pinball en pausa: controles y menú en la ventana del juego',
              null);
        }
        if (line == 'GAMECLUB_PINBALL_STATE running') {
          onProgress?.call('Pinball en juego', null);
        }
      });
      final stderr = process.stderr.forEach(log.add);
      final result = await process.exitCode;
      await Future.wait([stdout, stderr]);
      await windowManager.ensureInitialized();
      await windowManager.focus();
      if (result != 0) {
        throw Exception(
            'Visual Pinball cerró con error ($result). Revisa la ROM indicada y el registro ${preferences.path}.');
      }
    } finally {
      await log.close();
    }
  }
}
