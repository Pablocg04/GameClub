import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/integrated_player.dart';
import 'package:gameclub/main.dart';
import 'package:gameclub/player_host.dart';
import 'package:gameclub/television.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'player_test.dart' show evaluate, until, snapshot;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('modo móvil: autoarranque, mando cambia vídeo y menú con foco',
      (tester) async {
    await DevicePlatform.initialize();
    DevicePlatform.television = false;
    final api = GameClubApi('http://10.0.2.2:8687', '');
    final game = (await api.list('/api/games'))
        .firstWhere((game) => game['system_id'] == 'gb');
    final folder = Directory(
        p.join((await getTemporaryDirectory()).path, 'mobile-controller-test'));
    await folder.create(recursive: true);
    final rom = File(p.join(folder.path, game['filename'] as String));
    await api.dio.download('/api/games/${game['id']}/download', rom.path);
    final host = PlayerHost(Directory(p.join(folder.path, 'host')));
    await host.start(listenPort: 0);
    addTearDown(host.close);
    await tester.pumpWidget(GameClubApp(apiOverride: api, television: false));
    await tester.pump(const Duration(seconds: 2));
    final context = tester.element(find.byType(LibraryPage));
    final uri = host.open(game, rom, api, mobile: true, nativeGamepad: true);
    unawaited(Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => IntegratedPlayer(uri: uri, title: 'Prueba móvil'))));
    await until(tester, () async {
      try {
        return await evaluate(tester, '!!window.EJS_emulator?.started') == true;
      } catch (_) {
        return false;
      }
    }, timeout: const Duration(minutes: 4));
    expect(
        await evaluate(tester, '!!document.querySelector(".ejs_start_button")'),
        false);
    expect(find.byType(AppBar), findsNothing);
    final before =
        await snapshot(tester, File(p.join(folder.path, 'before.png')));
    await evaluate(tester,
        'window.__mobileA=false;const original=EJS_emulator.gameManager.simulateInput.bind(EJS_emulator.gameManager);EJS_emulator.gameManager.simulateInput=(player,index,value)=>{if(index===8&&value)window.__mobileA=true;return original(player,index,value);};true;');
    debugPrint('TV_BUTTON_A_READY');
    await until(
        tester, () async => await evaluate(tester, 'window.__mobileA') == true);
    final after =
        await snapshot(tester, File(p.join(folder.path, 'after.png')));
    expect(after.getBytes(), isNot(equals(before.getBytes())),
        reason: 'El programa de prueba no respondió al mando');
    await Future<void>.delayed(const Duration(seconds: 3));
    debugPrint('TV_MENU_READY');
    await until(
        tester, () async => find.text('Menú del juego').evaluate().isNotEmpty);
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú juego 0');
    debugPrint('TV_RESUME_READY');
    await until(
        tester, () async => find.text('Menú del juego').evaluate().isEmpty);
    debugPrint('TV_EXIT_READY');
    await until(
        tester, () async => find.text('Menú del juego').evaluate().isNotEmpty);
    debugPrint('TV_CONFIRM_EXIT_READY');
    await until(
        tester, () async => find.byType(IntegratedPlayer).evaluate().isEmpty);
    expect(
        (await DevicePlatform.channel
            .invokeMapMethod<String, dynamic>('info'))?['playerActive'],
        false);
    host.release(uri);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  }, timeout: const Timeout(Duration(minutes: 8)));
}
