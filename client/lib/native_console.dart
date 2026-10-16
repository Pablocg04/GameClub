import 'dart:io';
import 'package:archive/archive.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'api.dart';
import 'native_runtime.dart';
import 'game_files.dart';

const nativeConsoleCores = {'nes': 'nestopia', 'atari2600': 'stella'};
const nativeConsoleExtensions = {
  'nes': {'.nes', '.unf', '.unif'},
  'atari2600': {'.a26', '.bin', '.rom'},
};

class NativeConsole extends NativeRuntime {
  NativeConsole(super.api, {super.onProgress});

  /// Solo extrae una ROM reconocida; estados .sta y documentos no son juegos.
  static Future<File> unpack(
      String system, File source, Directory folder) async {
    final extensions = nativeConsoleExtensions[system];
    if (extensions == null) throw Exception('Consola nativa no disponible');
    await folder.create(recursive: true);
    if (p.extension(source.path).toLowerCase() != '.zip') {
      if (!extensions.contains(p.extension(source.path).toLowerCase())) {
        throw Exception('Formato de ROM no compatible con esta consola');
      }
      return source;
    }
    final archive = ZipDecoder().decodeBytes(await source.readAsBytes());
    final candidates = archive.files
        .where((member) =>
            member.isFile &&
            extensions.contains(p.extension(member.name).toLowerCase()))
        .toList();
    if (candidates.length != 1) {
      throw Exception(candidates.isEmpty
          ? 'El ZIP no contiene una ROM compatible. Los .sta son estados guardados.'
          : 'El ZIP contiene varios juegos. Usa una ROM o un ZIP por juego.');
    }
    final member = candidates.single;
    if (member.size == 0 || member.size > 64 * 1024 * 1024) {
      throw Exception('El tamaño de la ROM no es válido para esta consola');
    }
    // Nombre fijo: ninguna ruta del ZIP puede escribir fuera de su carpeta.
    final output = File(
        p.join(folder.path, 'game${p.extension(member.name).toLowerCase()}'));
    await output.writeAsBytes(member.content, flush: true);
    return output;
  }

  Future<File> prepare(Json game, Directory directory) async {
    final system = game['system_id'] as String;
    final extension = p.extension(game['filename'] as String).toLowerCase();
    if (!(nativeConsoleExtensions[system]?.contains(extension) ?? false) &&
        extension != '.zip') {
      throw Exception('Formato de ROM no compatible con esta consola');
    }
    await directory.create(recursive: true);
    final source = File(p.join(directory.path, 'source$extension'));
    await GameFiles.fetch(api, game, source,
        onProgress: (read, total) => onProgress?.call(
            'Preparando juego', total > 0 ? read / total : null));
    return unpack(system, source, directory);
  }

  Future<void> play(Json game,
      {bool? touchControls, bool diagnostics = false}) async {
    final name = nativeConsoleCores[game['system_id']];
    if (name == null) throw Exception('Consola nativa no disponible');
    final target = await platform();
    final support = await supportDirectory();
    onProgress?.call('Preparando ${game['system_id']} nativo…', null);
    final documents = await getApplicationDocumentsDirectory();
    final primary = await prepare(
        game,
        Directory(p.join(documents.path, 'GameClub', 'console-native',
            libraryKey, game['id'] as String)));
    final engine = await core(target, name, support, bundled: true);
    final saves = Directory(
        p.join(support.path, 'saves', libraryKey, game['id'] as String, name));
    await launch(engine, primary, saves,
        mode: game['system_id'] as String,
        touchControls: touchControls,
        diagnostics: diagnostics);
  }
}
