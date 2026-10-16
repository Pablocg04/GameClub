import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/arcade_loader.dart';
import 'package:gameclub/integrated_player.dart';
import 'package:gameclub/player_host.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:webview_windows/webview_windows.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'player_test.dart' show evaluate, until, snapshot;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Street Fighter II real: vídeo y controles dentro de GameClub',
      (tester) async {
    const server = String.fromEnvironment('PLAYER_TEST_SERVER',
        defaultValue: 'http://192.168.0.47:8001');
    final api = GameClubApi(server, '');
    final games = await api.list('/api/games');
    final game = games.firstWhere(
        (item) => item['system_id'] == 'mame' && item['filename'] == 'sf2.zip');
    final root = Directory(
        p.join((await getTemporaryDirectory()).path, 'gameclub-arcade-test'));
    final files = await ArcadeLoader(api, Directory(p.join(root.path, 'roms')))
        .prepare(game);
    final host = PlayerHost(Directory(p.join(root.path, 'host')));
    await host.start(listenPort: 0);
    final uri = host.open(game, files['sf2.zip']!, api,
        mobile: Platform.isAndroid,
        auxiliary: Map.fromEntries(
            files.entries.where((item) => item.key != 'sf2.zip')));
    addTearDown(() async {
      await host.close();
      api.dio.close();
    });
    await tester.pumpWidget(MaterialApp(
        home: IntegratedPlayer(uri: uri, title: 'Street Fighter II')));
    await until(
        tester,
        () async => Platform.isWindows
            ? find.byType(Webview).evaluate().isNotEmpty
            : find.byType(WebViewWidget).evaluate().isNotEmpty);
    await until(
        tester,
        () async =>
            await evaluate(
                tester, "!!document.querySelector('.ejs_start_button')") ==
            true);
    await evaluate(
        tester, "document.querySelector('.ejs_start_button').click()");
    await until(
        tester,
        () async =>
            await evaluate(tester, '!!window.EJS_emulator?.started') == true,
        timeout: const Duration(minutes: 5));
    await Future<void>.delayed(const Duration(seconds: 15));
    await tester.pump();
    final first =
        await snapshot(tester, File(p.join(root.path, 'sf2-start.png')));
    debugPrint('Arcade: vídeo recibido');
    final colours = <int>{};
    for (final pixel in first) {
      colours.add(
          (pixel.r.toInt() << 16) | (pixel.g.toInt() << 8) | pixel.b.toInt());
    }
    expect(first.width, greaterThan(200));
    expect(colours.length, greaterThan(32),
        reason:
            'La imagen debe contener vídeo arcade real, no una superficie vacía');
    await evaluate(tester,
        '''(() => {const parent=EJS_emulator.elements.parent; parent.focus();
      parent.dispatchEvent(new KeyboardEvent('keydown',{key:'v',code:'KeyV',keyCode:86,which:86,bubbles:true}));return true;})()''');
    await Future<void>.delayed(const Duration(milliseconds: 500));
    await evaluate(tester,
        '''(() => {EJS_emulator.elements.parent.dispatchEvent(new KeyboardEvent('keyup',{key:'v',code:'KeyV',keyCode:86,which:86,bubbles:true}));return true;})()''');
    debugPrint('Arcade: moneda enviada');
    await Future<void>.delayed(const Duration(seconds: 2));
    await evaluate(tester,
        '''(() => {EJS_emulator.elements.parent.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));return true;})()''');
    await Future<void>.delayed(const Duration(milliseconds: 500));
    await evaluate(tester,
        '''(() => {EJS_emulator.elements.parent.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));return true;})()''');
    debugPrint('Arcade: inicio enviado');
    await Future<void>.delayed(const Duration(seconds: 6));
    await tester.pump();
    final second =
        await snapshot(tester, File(p.join(root.path, 'sf2-playing.png')));
    debugPrint('Arcade: segundo fotograma recibido');
    expect(second.width, first.width);
    expect(await evaluate(tester, '!!EJS_emulator.failedToStart'), false);
    await tester.pumpWidget(const SizedBox());
    host.release(uri);
  }, timeout: const Timeout(Duration(minutes: 10)));
}
