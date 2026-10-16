import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/arcade_loader.dart';
import 'package:gameclub/integrated_player.dart';
import 'package:gameclub/main.dart';
import 'package:gameclub/player_host.dart';
import 'package:gameclub/television.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'player_test.dart' show evaluate, until, snapshot;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
      'Google TV: autoarranque, mando nativo, salida y navegación con teclado',
      (tester) async {
    await DevicePlatform.initialize();
    expect(DevicePlatform.television, true);
    expect(DevicePlatform.nativeGamepads, true);
    final api = GameClubApi('http://192.168.0.47:8001', '');
    const filename =
        String.fromEnvironment('TV_TEST_GAME', defaultValue: 'sf2.zip');
    final game = (await api.list('/api/games')).firstWhere(
        (g) => g['system_id'] == 'mame' && g['filename'] == filename);
    final directory = Directory(
        p.join((await getTemporaryDirectory()).path, 'tv-player-test'));
    await directory.create(recursive: true);
    const core =
        String.fromEnvironment('TV_TEST_CORE', defaultValue: 'mame2003_plus');
    final loader = ArcadeLoader(api, Directory(p.join(directory.path, 'roms')));
    final candidates = await loader.candidates(game);
    final plan = (candidates['candidates'] as List)
        .cast<Map>()
        .firstWhere((plan) => plan['core'] == core);
    final files =
        await loader.prepare(game, plan: Map<String, dynamic>.from(plan));
    final primary = '${plan['game_code']}.zip';
    final host = PlayerHost(Directory(p.join(directory.path, 'player')));
    await host.start(listenPort: 0);
    addTearDown(() async {
      await host.close();
    });
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pump(const Duration(seconds: 2));
    final context = tester.element(find.byType(LibraryPage));
    final uri = host.open({...game, 'filename': primary}, files[primary]!, api,
        arcadeCore: core,
        mobile: true,
        television: true,
        nativeGamepad: true,
        auxiliary: Map.fromEntries(
            files.entries.where((item) => item.key != primary)));
    unawaited(Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) =>
            IntegratedPlayer(uri: uri, title: 'Prueba Android TV'))));
    await until(tester, () async {
      try {
        return await evaluate(tester, '!!window.EJS_emulator?.started') == true;
      } catch (_) {
        return false;
      }
    }, timeout: const Duration(minutes: 4));
    // Una liberación tardía de un jugador anterior no debe capturar el actual.
    await DevicePlatform.channel.invokeMethod<void>('playerActive', {
      'active': false,
      'owner': 'stale-player-test',
      'restoreDisplay': true
    });
    expect(
        (await DevicePlatform.channel
            .invokeMapMethod<String, dynamic>('info'))?['playerActive'],
        true);
    if (const bool.fromEnvironment('TV_COMPARE_TIMING')) {
      for (final vsync in [true, false, true]) {
        await evaluate(
            tester, 'EJS_emulator.gameManager.setVSync($vsync);true;');
        await Future<void>.delayed(const Duration(seconds: 2));
        await evaluate(tester,
            'window.__timingSample={time:performance.now(),frames:EJS_emulator.gameManager.functions.getFrameNum(),presentation:window.gameclubPresentationFrames};true;');
        await Future<void>.delayed(const Duration(seconds: 6));
        final sample = await evaluate(tester,
                'JSON.stringify({emulationFps:(EJS_emulator.gameManager.functions.getFrameNum()-__timingSample.frames)*1000/(performance.now()-__timingSample.time),webViewFps:(window.gameclubPresentationFrames-__timingSample.presentation)*1000/(performance.now()-__timingSample.time)})')
            as Map;
        debugPrint('TV_TIMING $filename $core rAF=$vsync $sample');
        expect(sample['emulationFps'], greaterThan(0));
        expect(sample['webViewFps'], greaterThan(0));
      }
    }
    await evaluate(tester,
        '''window.__tvInputs=[];const original=EJS_emulator.gameManager.simulateInput.bind(EJS_emulator.gameManager);
      EJS_emulator.gameManager.simulateInput=(player,index,value)=>{window.__tvInputs.push({player,index,value});return original(player,index,value);};true;''');
    debugPrint('TV_INPUT_READY');
    await until(
        tester,
        () async =>
            await evaluate(tester,
                'window.__tvInputs.some(event=>event.index===2&&event.value===1)&&window.__tvInputs.some(event=>event.index===3&&event.value===1)&&window.__tvInputs.some(event=>event.index===7&&event.value===1)') ==
            true);
    await Future<void>.delayed(const Duration(seconds: 5));
    final frame =
        await snapshot(tester, File(p.join(directory.path, 'tv-playing.png')));
    expect(frame.width, greaterThan(200));
    debugPrint('TV_MENU_READY');
    await until(
        tester, () async => find.text('Menú del juego').evaluate().isNotEmpty);
    debugPrint('TV_RESUME_READY');
    await until(
        tester, () async => find.text('Menú del juego').evaluate().isEmpty);
    debugPrint('TV_EXIT_READY');
    await until(
        tester, () async => find.byType(IntegratedPlayer).evaluate().isEmpty);
    expect(
        (await DevicePlatform.channel
            .invokeMapMethod<String, dynamic>('info'))?['playerActive'],
        false);
    debugPrint('TV_LIBRARY_RB_READY');
    await until(
        tester,
        () async =>
            FocusManager.instance.primaryFocus?.debugLabel == 'Menú TV 1');
    debugPrint('TV_LIBRARY_LB_READY');
    await until(
        tester,
        () async =>
            FocusManager.instance.primaryFocus?.debugLabel == 'Menú TV 0');
    debugPrint('TV_SEARCH_READY');
    await until(
        tester,
        () async =>
            FocusManager.instance.primaryFocus?.debugLabel == 'Buscar TV');
    debugPrint('TV_SEARCH_TEXT_READY');
    await until(
        tester,
        () async => find.byType(EditableText).evaluate().any((element) =>
            (element.widget as EditableText).controller.text == 'sf2'));
    debugPrint('TV_SEARCH_COMPLETE');
    host.release(uri);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  }, timeout: const Timeout(Duration(minutes: 10)));
}
