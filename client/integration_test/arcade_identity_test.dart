import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/arcade_loader.dart';
import 'package:gameclub/arcade_player.dart';
import 'package:gameclub/integrated_player.dart';
import 'package:gameclub/player_host.dart';
import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';
import 'player_test.dart' show evaluate, until, snapshot;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
      'Super Basketball H se identifica por CRC y arranca como sbasketh',
      (tester) async {
    final api = GameClubApi('http://192.168.0.47:8001', '');
    final game = (await api.list('/api/games')).firstWhere(
        (g) => g['filename'] == 'sbasketb.zip' && g['system_id'] == 'mame');
    final root = Directory(
        r'C:\Users\pablo\AppData\Local\Temp\opencode\gameclub-identity-test');
    await root.create(recursive: true);
    final loader = ArcadeLoader(api, Directory(p.join(root.path, 'roms')));
    final preferences = await SharedPreferences.getInstance();
    final key = loader.preferenceKey(game),
        previous = preferences.getString(loader.preferenceKey(game));
    final result = await loader.candidates(game);
    final plans = result['candidates'] as List<Json>;
    final plan = plans.firstWhere((item) => item['core'] == 'fbneo');
    expect(plan['game_code'], 'sbasketh');
    expect(plan['identified_by'], 'content');
    final host = PlayerHost(Directory(p.join(root.path, 'host')));
    await host.start(listenPort: 0);
    addTearDown(() async {
      await host.close();
      api.dio.close();
      if (previous == null) {
        await preferences.remove(key);
      } else {
        await preferences.setString(key, previous);
      }
    });
    await tester.pumpWidget(MaterialApp(
        home: ArcadePlayer(
            game: game, loader: loader, host: host, api: api, plans: plans)));
    await until(tester, () async {
      try {
        return await evaluate(
                tester, "!!document.querySelector('.ejs_start_button')") ==
            true;
      } catch (_) {
        return false;
      }
    });
    await evaluate(
        tester, "document.querySelector('.ejs_start_button').click();true;");
    await until(tester, () async {
      if (find
          .text('Ningún núcleo disponible pudo iniciar este romset.')
          .evaluate()
          .isNotEmpty) {
        throw StateError(tester.allWidgets
            .whereType<Text>()
            .map((value) => value.data ?? '')
            .join(' | '));
      }
      return preferences.getString(key)?.contains('"core":"fbneo"') == true;
    }, timeout: const Duration(minutes: 4));
    await Future<void>.delayed(const Duration(seconds: 8));
    final image =
        await snapshot(tester, File(p.join(root.path, 'super-basketball.png')));
    expect(host.sessions.values.single.game['filename'], 'sbasketh.zip');
    expect(
        await evaluate(tester,
            "EJS_emulator.gameManager.FS.stat('/roms/sbasketh.zip').size"),
        game['size']);
    final colors = <int>{};
    for (final pixel in image) {
      colors
          .add(pixel.r.toInt() << 16 | pixel.g.toInt() << 8 | pixel.b.toInt());
    }
    expect(colors.length, greaterThan(8));
    debugPrint(
        'Super Basketball H: ${image.width}x${image.height}, ZIP original sbasketb, driver sbasketh');
    expect(find.byType(IntegratedPlayer), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  }, timeout: const Timeout(Duration(minutes: 8)));
}
