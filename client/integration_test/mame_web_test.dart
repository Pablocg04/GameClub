import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/arcade_loader.dart';
import 'package:gameclub/arcade_player.dart';
import 'package:gameclub/main.dart';
import 'package:gameclub/player_host.dart';
import 'package:gameclub/integrated_player.dart';
import 'package:gameclub/television.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'player_test.dart' show evaluate, until, snapshot;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  for (final code in ['barline', 'cfever61', 'rcasino']) {
    testWidgets('MAME 0.232 integrado: $code, controles y archivos de guardado',
        (tester) async {
      final api = GameClubApi('http://192.168.0.47:8001', '');
      await DevicePlatform.initialize();
      await tester.pumpWidget(const SizedBox.shrink());
      final game = (await api.list('/api/games'))
          .firstWhere((item) => item['filename'] == '$code.zip');
      final root = Directory(p.join((await getTemporaryDirectory()).path,
          'gameclub-mame-web-test', code));
      await root.create(recursive: true);
      final loader = ArcadeLoader(api, Directory(p.join(root.path, 'roms')));
      final prefs = await SharedPreferences.getInstance();
      final key = loader.preferenceKey(game),
          previous = prefs.getString(loader.preferenceKey(game));
      final result = await loader.candidates(game);
      final plans = result['candidates'] as List<Json>;
      expect(plans.any((plan) => plan['core'] == 'mame_web'), true);
      final host = PlayerHost(Directory(p.join(root.path, 'host')));
      await host.start(listenPort: 0);
      addTearDown(() async {
        await host.close();
        if (previous == null) {
          await prefs.remove(key);
        } else {
          await prefs.setString(key, previous);
        }
      });
      await tester.pumpWidget(GameClubApp(apiOverride: api));
      await tester.pump(const Duration(seconds: 1));
      final context = tester.element(find.byType(LibraryPage));
      unawaited(Navigator.of(context).push(MaterialPageRoute<void>(
          builder: (_) => ArcadePlayer(
              game: game,
              loader: loader,
              host: host,
              api: api,
              plans: plans))));
      if (!DevicePlatform.television) {
        await until(tester, () async {
          try {
            return await evaluate(
                    tester, "!!document.querySelector('.ejs_start_button')") ==
                true;
          } catch (_) {
            return false;
          }
        });
        await evaluate(tester,
            "document.querySelector('.ejs_start_button').click();true;");
      }
      await until(
          tester,
          () async =>
              prefs.getString(key)?.contains('"core":"mame_web"') == true,
          timeout: const Duration(minutes: 4));
      await Future<void>.delayed(const Duration(seconds: 8));
      final frame =
          await snapshot(tester, File(p.join(root.path, 'running.png')));
      final colors = <int>{};
      for (final pixel in frame) {
        colors.add(
            pixel.r.toInt() << 16 | pixel.g.toInt() << 8 | pixel.b.toInt());
      }
      expect(colors.length, greaterThan(3));
      await evaluate(
          tester, "EJS_emulator.gameManager.toggleMainLoop(0);true;");
      await evaluate(
          tester, "EJS_emulator.gameManager.toggleMainLoop(1);true;");
      await evaluate(tester, "JSMAME.sdl_sendkeyboardkey(1,34);true;");
      await Future<void>.delayed(const Duration(milliseconds: 200));
      await evaluate(tester, "JSMAME.sdl_sendkeyboardkey(0,34);true;");
      final session = host.sessions.values.single;
      await evaluate(tester, "window.gameclubExit();true;");
      await until(
          tester, () async => find.byType(IntegratedPlayer).evaluate().isEmpty);
      expect(await host.battery(session).exists(), true);
      debugPrint(
          '$code: vídeo ${frame.width}x${frame.height}, ${colors.length} colores y guardado confirmado');
      await tester.pumpWidget(const SizedBox.shrink());
    }, timeout: const Timeout(Duration(minutes: 8)));
  }
}
