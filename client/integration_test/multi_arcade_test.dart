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

class MissingBiosLoader extends ArcadeLoader {
  MissingBiosLoader(super.api, super.directory);
  @override
  Future<Map<String, File>> prepare(Json game, {Json? plan}) async {
    final files = await super.prepare(game, plan: plan);
    files.remove('neogeo.zip');
    return files;
  }
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  for (final scenario in [
    ('mslug.zip', false),
    ('sf2.zip', false),
    ('mslug.zip', true)
  ]) {
    final (filename, missingBios) = scenario;
    testWidgets(
        'arcade automático real: $filename ${missingBios ? 'sin BIOS' : ''}',
        (tester) async {
      const base = String.fromEnvironment('PLAYER_TEST_SERVER',
          defaultValue: 'http://192.168.0.47:8001');
      const output = String.fromEnvironment('PLAYER_TEST_OUTPUT',
          defaultValue:
              r'C:\Users\pablo\AppData\Local\Temp\opencode\gameclub-multi-arcade-test');
      final api = GameClubApi(base, '');
      final game = (await api.list('/api/games')).firstWhere(
          (g) => g['filename'] == filename && g['system_id'] == 'mame');
      final directory = Directory(p.join(
          output,
          p.basenameWithoutExtension(filename) +
              (missingBios ? '-missing-bios' : '')));
      await directory.create(recursive: true);
      final loader = missingBios
          ? MissingBiosLoader(api, Directory(p.join(directory.path, 'roms')))
          : ArcadeLoader(api, Directory(p.join(directory.path, 'roms')));
      final preferences = await SharedPreferences.getInstance();
      final key = loader.preferenceKey(game),
          previous = preferences.getString(loader.preferenceKey(game));
      await loader.forget(game);
      final result = await loader.candidates(game);
      final plans = result['candidates'] as List<Json>;
      if (filename == 'sf2.zip') {
        final first = plans.indexWhere((plan) => plan['core'] == 'fbneo');
        plans.insert(0, plans.removeAt(first));
      }
      expect(plans, isNotEmpty);
      final host = PlayerHost(Directory(p.join(directory.path, 'host')));
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
      await until(tester,
          () async => find.byType(IntegratedPlayer).evaluate().isNotEmpty);
      await until(tester, () async {
        try {
          return await evaluate(
                  tester, "!!document.querySelector('.ejs_start_button')") ==
              true;
        } catch (_) {
          return false;
        }
      });
      if (filename == 'sf2.zip') {
        // Fallo controlado del primer intento: debe cambiar solo al siguiente,
        // arrancarlo automáticamente y descartar la sesión anterior.
        final old = host.sessions.keys.single;
        tester
            .widget<IntegratedPlayer>(find.byType(IntegratedPlayer))
            .onCoreFailed!('Fallo de arranque simulado');
        await until(
            tester,
            () async =>
                host.sessions.length == 1 && !host.sessions.containsKey(old));
      } else {
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
      final target = filename == 'mslug.zip' ? 'fbneo' : 'mame2003_plus';
      if (missingBios) {
        await until(
            tester,
            () async =>
                find
                    .text('Ningún núcleo disponible pudo iniciar este romset.')
                    .evaluate()
                    .isNotEmpty ||
                preferences.getString(key) != null);
        if (preferences.getString(key) != null) {
          final frame =
              await snapshot(tester, File(p.join(directory.path, 'error.png')));
          var hash = 2166136261;
          for (var y = 0; y < 14; y++) {
            for (var x = 0; x < 112; x++) {
              final pixel = frame.getPixel(x, y);
              for (final value in [
                pixel.r.toInt(),
                pixel.g.toInt(),
                pixel.b.toInt(),
                255
              ]) {
                hash = ((hash ^ value) * 16777619) & 0xffffffff;
              }
            }
          }
          debugPrint('Firma de cabecera FBNeo Error: $hash');
        }
        expect(preferences.getString(key), isNull,
            reason: 'Una pantalla FBNeo Error no debe recordarse como éxito');
        await tester.pumpWidget(const SizedBox.shrink());
        return;
      }
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
        return preferences.getString(key)?.contains('"core":"$target"') == true;
      }, timeout: const Duration(minutes: 5));
      await Future<void>.delayed(const Duration(seconds: 15));
      final image =
          await snapshot(tester, File(p.join(directory.path, 'running.png')));
      final colours = <int>{};
      for (final pixel in image) {
        colours.add(
            pixel.r.toInt() << 16 | pixel.g.toInt() << 8 | pixel.b.toInt());
      }
      expect(colours.length, greaterThan(32));
      expect(host.sessions.values.single.arcadeCore, target);
      if (filename == 'mslug.zip') {
        expect(
            await evaluate(tester,
                "EJS_emulator.gameManager.FS.analyzePath('/roms/neogeo.zip').exists"),
            true);
        expect(
            await evaluate(tester,
                "EJS_emulator.gameManager.FS.stat('/roms/neogeo.zip').size"),
            greaterThan(1000));
      }
      final reordered =
          (await loader.candidates(game))['candidates'] as List<Json>;
      expect(reordered.first['core'], target);
      debugPrint(
          '$filename: núcleo $target, vídeo ${image.width}x${image.height}, preferencia confirmada');
      await tester.pumpWidget(const SizedBox.shrink());
    }, timeout: const Timeout(Duration(minutes: 10)));
  }
}
