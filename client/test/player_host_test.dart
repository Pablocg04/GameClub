import 'dart:convert';
import 'dart:io';

import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/player_host.dart';
import 'package:path/path.dart' as p;

void main() {
  test(
      'perfil TV permite comparar rAF y bucle inmediato sin afectar al escritorio',
      () {
    final game = {'id': '123abc', 'system_id': 'gb', 'filename': 'test.gb'};
    final api = GameClubApi('http://test', '');
    final fast = PlayerHost.playerHtml(
        PlayerSession('s', game, File('test.gb'), api, true, television: true));
    final balanced = PlayerHost.playerHtml(PlayerSession(
        's', game, File('test.gb'), api, true,
        television: true, fastTelevision: false));
    final desktop = PlayerHost.playerHtml(
        PlayerSession('s', game, File('test.gb'), api, false));
    expect(fast, contains('video_vsync = true'));
    expect(fast, contains('gameManager.setVSync(true)'));
    final immediate = PlayerHost.playerHtml(PlayerSession(
        's', game, File('test.gb'), api, true,
        television: true, tvVsync: false));
    expect(immediate, contains('gameManager.setVSync(false)'));
    expect(fast, contains('"tv-fast"'));
    expect(balanced, isNot(contains('gameManager.setVSync(false)')));
    expect(desktop, isNot(contains('video_vsync = false')));
  });
  test('MAME web guarda y restaura NVRAM y configuración dentro de su sesión',
      () async {
    final folder = await Directory.systemTemp.createTemp('gameclub-mame-save-');
    final host = PlayerHost(folder);
    addTearDown(() async {
      await host.close();
      await folder.delete(recursive: true);
    });
    final rom = File(p.join(folder.path, 'barline.zip'));
    await rom.writeAsBytes([1]);
    await host.start(listenPort: 0);
    final uri = host.open(
        {'id': '123abc', 'system_id': 'mame', 'filename': 'barline.zip'},
        rom,
        GameClubApi('http://test', 'secret'),
        mobile: false,
        arcadeCore: 'mame_web',
        mameDriver: 'nbmj8688');
    final http = HttpClient();
    addTearDown(http.close);
    final endpoint = uri.resolve('mame-save');
    final request = await http.postUrl(endpoint);
    request.headers.contentType = ContentType.json;
    request.write(jsonEncode({
      'nvram/barline/nvram': base64Encode([1, 2, 3]),
      'cfg/barline.cfg': base64Encode([4, 5])
    }));
    expect((await request.close()).statusCode, 204);
    final response = await (await http.getUrl(endpoint)).close();
    final data = jsonDecode(await utf8.decoder.bind(response).join()) as Map;
    expect(base64Decode(data['nvram/barline/nvram'] as String), [1, 2, 3]);
    expect(base64Decode(data['cfg/barline.cfg'] as String), [4, 5]);
    final unsafe = await http.postUrl(endpoint);
    unsafe.write(jsonEncode({
      'cfg/../../outside': base64Encode([99])
    }));
    expect((await unsafe.close()).statusCode, 502);
    final archive = ZipDecoder().decodeBytes(
        await host.battery(host.sessions.values.single).readAsBytes());
    expect(archive.files.length, 2);
    host.release(uri);
    expect((await (await http.getUrl(endpoint)).close()).statusCode, 404);
  });
  test(
      'el reproductor sirve la ROM solo a su sesión y mantiene un origen local',
      () async {
    final folder = await Directory.systemTemp.createTemp('gameclub-player-');
    final host = PlayerHost(folder);
    addTearDown(() async {
      await host.close();
      await folder.delete(recursive: true);
    });
    final rom = File(p.join(folder.path, 'test.nds'));
    await rom.writeAsBytes([1, 2, 3]);
    await host.start(listenPort: 0);
    final api = GameClubApi('http://test', 'private-token');
    final uri = host.open(
        {'id': '123abc', 'system_id': 'nds', 'filename': 'test.nds'}, rom, api,
        mobile: true);
    final http = HttpClient();
    addTearDown(http.close);
    final page = await (await http.getUrl(uri)).close();
    final html = await utf8.decoder.bind(page).join();
    expect(html, contains('"desmume"'));
    expect(html, isNot(contains('private-token')));
    expect(page.headers.value('cross-origin-opener-policy'), 'same-origin');
    final url = uri.resolve('rom/test.nds');
    final response = await (await http.getUrl(url)).close();
    expect(await response.fold<List<int>>([], (all, part) => all..addAll(part)),
        [1, 2, 3]);
    final save = await http.postUrl(uri
        .resolve('battery')
        .replace(queryParameters: {'path': 'DeSmuME/Juego (España).dsv'}));
    save.add([11, 22, 33]);
    expect((await save.close()).statusCode, 204);
    final restored = await (await http.getUrl(uri)).close();
    final restoredHtml = await utf8.decoder.bind(restored).join();
    expect(restoredHtml, contains('EJS_externalFiles'));
    final bundle =
        await (await http.getUrl(uri.resolve('battery.zip'))).close();
    final data =
        await bundle.fold<List<int>>([], (all, part) => all..addAll(part));
    final archive = ZipDecoder().decodeBytes(data);
    expect(archive.files.single.name, 'DeSmuME/Juego (España).dsv');
    expect(archive.files.single.content, [11, 22, 33]);
    final overwrite = await http.postUrl(uri
        .resolve('battery')
        .replace(queryParameters: {'path': 'DeSmuME/Juego (España).dsv'}));
    overwrite.add([44, 55, 66]);
    expect((await overwrite.close()).statusCode, 204);
    final unsafe = await http.postUrl(uri
        .resolve('battery')
        .replace(queryParameters: {'path': '../escape.srm'}));
    unsafe.add([99]);
    expect((await unsafe.close()).statusCode, 422);
    host.release(uri);
    expect((await (await http.getUrl(url)).close()).statusCode, 404);
  });

  test('la configuración de los motores integrados es común y segura', () {
    expect(integratedCores.keys,
        containsAll(['gb', 'gbc', 'gba', 'snes', 'nds', 'n64']));
    final session = PlayerSession(
        'session',
        {'id': '123abc', 'system_id': 'gba', 'filename': 'test.gba'},
        File('test.gba'),
        GameClubApi('http://test', ''),
        false);
    final html = PlayerHost.playerHtml(session);
    expect(html, contains('"mgba"'));
    expect(html, contains("'save-state-location':'browser'"));
    expect(html, contains('gameclub_123abc'));
    expect(html, contains('Volver a GameClub'));
  });

  test('perfil rápido NDS reduce carga y detecta multihilo sin forzar JIT', () {
    final session = PlayerSession(
        'session',
        {
          'id': '123abc',
          'system_id': 'nds',
          'filename': 'Mario Kart DS.nds',
          'size': 33554432
        },
        File('test.nds'),
        GameClubApi('http://test', ''),
        true,
        ndsProfile: 'fast');
    final html = PlayerHost.playerHtml(session);
    expect(html, contains("'desmume_frameskip':\"1\""));
    expect(html, contains("'desmume_advanced_timing':\"disabled\""));
    expect(html, contains('window.crossOriginIsolated'));
    expect(html, contains('typeof SharedArrayBuffer'));
    expect(html, isNot(contains("'desmume_cpu_mode':'jit'")));
  });
}
