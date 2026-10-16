import 'dart:convert';
import 'dart:io';
import 'package:archive/archive.dart';
import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:window_manager/window_manager.dart';
import 'api.dart';
import 'television.dart';

/// Caché verificada y ejecución compartida por arcade, NES y Atari 2600.
class NativeRuntime {
  NativeRuntime(this.api, {this.onProgress});
  final GameClubApi api;
  final void Function(String, double?)? onProgress;

  String get libraryKey =>
      api.dio.options.baseUrl.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_');

  Future<String> platform() async {
    if (Platform.isWindows) return 'windows-x86_64';
    if (Platform.isAndroid) {
      return (await DevicePlatform.channel
          .invokeMethod<String>('nativePlatform'))!;
    }
    throw Exception(
        'El reproductor nativo está disponible en Windows y Android');
  }

  Future<Directory> supportDirectory() async => Directory(
      p.join((await getApplicationSupportDirectory()).path, 'native'));

  static Future<String> fileHash(File file) async =>
      (await sha256.bind(file.openRead()).first).toString();

  Future<File> core(String platform, String name, Directory directory,
      {bool bundled = false}) async {
    final Json metadata = bundled
        ? Json.from(jsonDecode(
                await rootBundle.loadString('assets/native_console_cores.json'))
            as Map)
        : (await api.dio.get<Json>('/api/player/native')).data!;
    final entry =
        ((metadata['platforms'] as Map)[platform] as Map?)?[name] as Map?;
    if (entry == null) {
      throw Exception('Este motor no está disponible para $platform');
    }
    final folder = Directory(p.join(
        directory.path, 'cores', metadata['version'] as String, platform));
    await folder.create(recursive: true);
    final binary = File(p.join(folder.path, entry['binary'] as String));
    if (await binary.exists() &&
        await binary.length() == entry['binary_size'] &&
        await fileHash(binary) == entry['binary_sha256']) {
      return binary;
    }
    final zipped = File(p.join(folder.path, '$name.zip'));
    if (!await zipped.exists() ||
        await zipped.length() != entry['size'] ||
        await fileHash(zipped) != entry['sha256']) {
      final partial = '${zipped.path}.part';
      try {
        if (bundled) {
          final bytes =
              await rootBundle.load('assets/native-cores/$platform/$name.zip');
          await File(partial).writeAsBytes(
              bytes.buffer
                  .asUint8List(bytes.offsetInBytes, bytes.lengthInBytes),
              flush: true);
        } else {
          await api.dio.download('/api/player/native/$platform/$name', partial,
              options: Options(receiveTimeout: const Duration(minutes: 10)),
              onReceiveProgress: (read, total) => onProgress?.call(
                  'Descargando motor nativo $name',
                  total > 0 ? read / total : null));
        }
        if (await File(partial).length() != entry['size'] ||
            await fileHash(File(partial)) != entry['sha256']) {
          throw Exception('El archivo del motor no coincide con su huella');
        }
        if (await zipped.exists()) await zipped.delete();
        await File(partial).rename(zipped.path);
      } finally {
        if (await File(partial).exists()) await File(partial).delete();
      }
    }
    final archive = ZipDecoder().decodeBytes(await zipped.readAsBytes());
    final member = archive.find(entry['binary'] as String);
    if (member == null || member.size != entry['binary_size']) {
      throw Exception('Archivo de motor incompleto');
    }
    final temporary = File('${binary.path}.part');
    await temporary.writeAsBytes(member.content, flush: true);
    if (await fileHash(temporary) != entry['binary_sha256']) {
      await temporary.delete();
      throw Exception('Motor nativo dañado');
    }
    if (await binary.exists()) await binary.delete();
    await temporary.rename(binary.path);
    return binary;
  }

  Future<void> launch(File engine, File primary, Directory saves,
      {String mode = 'arcade',
      bool? touchControls,
      bool diagnostics = false}) async {
    await saves.create(recursive: true);
    final report = File(p.join(saves.path, 'session.txt'));
    if (await report.exists()) await report.delete();
    if (diagnostics) {
      for (final suffix in ['.bmp', '.after.bmp', '.engine', '.layout']) {
        final file = File('${report.path}$suffix');
        if (await file.exists()) await file.delete();
      }
    }
    final arguments = [
      engine.path,
      primary.path,
      saves.path,
      report.path,
      (touchControls ?? (Platform.isAndroid && !DevicePlatform.television))
          ? 'touch'
          : 'pad',
      mode,
      if (diagnostics) 'verify'
    ];
    if (Platform.isAndroid) {
      await DevicePlatform.channel.invokeMethod<void>('playNative', {
        'arguments': arguments,
        'orientation': DevicePlatform.mobileOrientation,
        'touchScale': DevicePlatform.touchScale
      });
    } else {
      final executable = File(p.join(
          p.dirname(Platform.resolvedExecutable), 'gameclub_native.exe'));
      if (!await executable.exists()) {
        throw Exception('Falta gameclub_native.exe en el paquete de GameClub');
      }
      final process = await Process.start(executable.path, arguments,
          workingDirectory: primary.parent.path);
      process.stdout.drain<void>();
      process.stderr.drain<void>();
      await process.exitCode;
      await windowManager.ensureInitialized();
      await windowManager.focus();
    }
    // SDL puede estar terminando de cerrar sus archivos al devolver el resultado.
    var outcome = '';
    for (var attempt = 0; attempt < 50; attempt++) {
      if (await report.exists()) outcome = await report.readAsString();
      if (outcome.startsWith('closed\n') || outcome.startsWith('error\n')) {
        break;
      }
      await Future<void>.delayed(const Duration(milliseconds: 100));
    }
    if (!outcome.startsWith('closed\n')) {
      final message = outcome.split('\n').skip(1).join('\n').trim();
      throw Exception(
          message.isEmpty ? 'El motor no pudo arrancar el juego' : message);
    }
  }
}
