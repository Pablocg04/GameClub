import 'dart:io';
import 'package:path/path.dart' as p;
import 'api.dart';

/// Las ROMs cacheadas se invalidan por revisión, incluso si su tamaño no cambia.
class GameFiles {
  static String libraryKey(GameClubApi api) =>
      api.dio.options.baseUrl.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_');

  static Future<File> fetch(GameClubApi api, Json game, File file,
      {void Function(int, int)? onProgress}) async {
    final version = game['revision']?.toString() ?? 'legacy';
    final marker = File('${file.path}.revision');
    if (await file.exists() &&
        await file.length() == game['size'] &&
        await marker.exists() &&
        await marker.readAsString() == version) {
      return file;
    }
    await file.parent.create(recursive: true);
    final temporary = File('${file.path}.part');
    try {
      await api.dio.download(
          '/api/games/${game['id']}/download', temporary.path,
          onReceiveProgress: onProgress);
      if (await temporary.length() != game['size']) {
        throw Exception(
            'Descarga incompleta. Vuelve a escanear la biblioteca.');
      }
      if (await file.exists()) await file.delete();
      await temporary.rename(file.path);
      await marker.writeAsString(version, flush: true);
      return file;
    } finally {
      if (await temporary.exists()) await temporary.delete();
    }
  }

  static File location(GameClubApi api, Json game, Directory documents) =>
      File(p.join(documents.path, 'GameClub', 'games', libraryKey(api),
          game['id'] as String, p.basename(game['filename'] as String)));
}
