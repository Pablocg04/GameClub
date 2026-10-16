import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/arcade_loader.dart';
import 'package:shared_preferences/shared_preferences.dart';

class CoresAdapter implements HttpClientAdapter {
  String signature = 'same';
  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? stream,
          Future<void>? cancel) async =>
      ResponseBody.fromString(
          jsonEncode({
            'candidates': [
              {
                'core': 'mame2003_plus',
                'signature': signature,
                'engine_version': '4.2.3'
              },
              {
                'core': 'fbneo',
                'signature': signature,
                'engine_version': '4.2.3'
              }
            ],
            'rejected': []
          }),
          200,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType]
          });
  @override
  void close({bool force = false}) {}
}

void main() {
  test('recuerda el núcleo por juego y dispositivo e invalida ROMs cambiadas',
      () async {
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    final adapter = CoresAdapter();
    api.dio.httpClientAdapter = adapter;
    final loader = ArcadeLoader(api, Directory.systemTemp);
    final game = <String, dynamic>{'id': 'test'};
    final original =
        (await loader.candidates(game))['candidates'] as List<Json>;
    await loader.remember(game, original[1]);
    expect(
        ((await loader.candidates(game))['candidates'] as List<Json>)
            .first['core'],
        'fbneo');
    adapter.signature = 'updated';
    expect(
        ((await loader.candidates(game))['candidates'] as List<Json>)
            .first['core'],
        'mame2003_plus');
    adapter.signature = 'same';
    await loader.forget(game);
    expect(
        ((await loader.candidates(game))['candidates'] as List<Json>)
            .first['core'],
        'mame2003_plus');
    api.dio.close();
  });
}
