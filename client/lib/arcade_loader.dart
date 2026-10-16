import 'dart:convert';
import 'dart:io';
import 'package:path/path.dart' as p;
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api.dart';

class ArcadeLoader {
  ArcadeLoader(this.api, this.directory, {this.onProgress});
  final GameClubApi api;
  final Directory directory;
  final void Function(String, double?)? onProgress;

  String preferenceKey(Json game, {bool native = false}) =>
      'arcade-core:${api.dio.options.baseUrl}:${game['id']}:${Platform.operatingSystem}${native ? ':native-1' : ''}';

  Future<Json> candidates(Json game, {bool native = false}) async {
    onProgress?.call('Buscando núcleos compatibles…', null);
    final response = await api.dio.get<Json>(
        '/api/games/${game['id']}/arcade/cores',
        queryParameters: {
          'identify': true,
          if (native) 'native': true else 'web_mame': true
        },
        options: Options(receiveTimeout: const Duration(minutes: 5)));
    final result = response.data!;
    final plans = (result['candidates'] as List)
        .map((value) => Json.from(value as Map))
        .toList();
    final preferences = await SharedPreferences.getInstance();
    final saved = preferences.getString(preferenceKey(game, native: native));
    if (saved != null) {
      try {
        final previous = jsonDecode(saved) as Map;
        final index = plans.indexWhere((plan) =>
            plan['core'] == previous['core'] &&
            plan['signature'] == previous['signature'] &&
            plan['engine_version'] == previous['engine_version']);
        if (index > 0) plans.insert(0, plans.removeAt(index));
      } on FormatException {/* Una preferencia antigua no impide jugar. */}
    }
    return {...result, 'candidates': plans};
  }

  Future<void> remember(Json game, Json plan, {bool native = false}) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(
        preferenceKey(game, native: native),
        jsonEncode({
          'core': plan['core'],
          'signature': plan['signature'],
          'engine_version': plan['engine_version']
        }));
  }

  Future<void> forget(Json game, {bool native = false}) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(preferenceKey(game, native: native));
  }

  Future<Map<String, File>> prepare(Json game, {Json? plan}) async {
    final Json manifest;
    if (plan != null) {
      manifest = plan;
    } else {
      manifest =
          (await api.dio.get<Json>('/api/games/${game['id']}/arcade')).data!;
    }
    await directory.create(recursive: true);
    final index = File(p.join(directory.path, '.assets.json'));
    Json saved = {};
    if (await index.exists()) {
      try {
        saved = Json.from(jsonDecode(await index.readAsString()) as Map);
      } on FormatException {
        saved = {};
      }
    }
    final files = <String, File>{};
    for (final raw in manifest['files'] as List) {
      final item = Json.from(raw as Map);
      final destination = item['destination'] as String;
      if (destination.startsWith('/') ||
          destination.contains('\\') ||
          destination.contains(':') ||
          destination
              .split('/')
              .any((part) => {'', '.', '..'}.contains(part))) {
        throw Exception('Ruta arcade inválida');
      }
      final file = File(p.joinAll([directory.path, ...destination.split('/')]));
      final previous = saved[destination] as Map?;
      if (!await file.exists() ||
          await file.length() != item['size'] ||
          previous?['modified'] != item['modified']) {
        await file.parent.create(recursive: true);
        final temp = File('${file.path}.part');
        try {
          final query =
              Uri(queryParameters: {'path': item['path'] as String}).query;
          await api.dio.download('/api/mame/download?$query', temp.path,
              onReceiveProgress: (read, total) => onProgress?.call(
                  'Preparando $destination', total > 0 ? read / total : null));
          if (await temp.length() != item['size']) {
            throw Exception('Descarga arcade incompleta');
          }
          await temp.rename(file.path);
        } finally {
          if (await temp.exists()) await temp.delete();
        }
        saved[destination] = {
          'size': item['size'],
          'modified': item['modified']
        };
      }
      files[destination] = file;
    }
    await index.writeAsString(jsonEncode(saved), flush: true);
    if (!files.containsKey('${manifest['game_code']}.zip')) {
      throw Exception('Falta el ZIP principal');
    }
    return files;
  }
}
