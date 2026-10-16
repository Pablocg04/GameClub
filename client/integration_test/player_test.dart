import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/integrated_player.dart';
import 'package:gameclub/player_host.dart';
import 'package:image/image.dart' as image;
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_windows/webview_windows.dart';

Future<dynamic> evaluate(WidgetTester tester, String script) async {
  dynamic result;
  if (Platform.isWindows) {
    result = await tester
        .widget<Webview>(find.byType(Webview))
        .controller
        .executeScript(script);
  } else {
    result = await tester
        .widget<WebViewWidget>(find.byType(WebViewWidget))
        .platform
        .params
        .controller
        .runJavaScriptReturningResult(script);
  }
  while (result is String) {
    try {
      result = jsonDecode(result);
    } on FormatException {
      break;
    }
  }
  return result;
}

Future<void> until(WidgetTester tester, Future<bool> Function() predicate,
    {Duration timeout = const Duration(minutes: 3)}) async {
  final end = DateTime.now().add(timeout);
  while (DateTime.now().isBefore(end)) {
    await tester.pump(const Duration(milliseconds: 200));
    if (await predicate()) return;
    await Future<void>.delayed(const Duration(milliseconds: 200));
  }
  final texts =
      tester.allWidgets.whereType<Text>().map((w) => w.data ?? '').join(' | ');
  String details = '';
  try {
    details = (await evaluate(tester, 'document.body.innerText')).toString();
  } catch (_) {}
  throw StateError('Tiempo agotado. $texts | $details');
}

Future<image.Image> snapshot(WidgetTester tester, File output) async {
  await evaluate(tester, '''window.__gameclubShot = null;
    EJS_emulator.gameManager.screenshot().then(bytes => {
      let text = ''; for (const value of new Uint8Array(bytes)) text += String.fromCharCode(value);
      window.__gameclubShot = btoa(text);
    });''');
  await until(tester,
      () async => (await evaluate(tester, 'window.__gameclubShot')) is String);
  final bytes =
      base64Decode(await evaluate(tester, 'window.__gameclubShot') as String);
  await output.writeAsBytes(bytes);
  return image.decodePng(bytes)!;
}

TestGesture? touchButton;

Future<void> pressA(WidgetTester tester, bool pressed) async {
  if (Platform.isAndroid) {
    if (pressed) {
      await until(tester, () async => await evaluate(tester, '''(() => {
        const button=document.querySelector('.ejs_virtualGamepad_button.b_a');
        if(!button) return false; const r=button.getBoundingClientRect();
        return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===button;
      })()''') == true);
      final rect = await evaluate(tester, '''JSON.stringify((() => {
        const button=document.querySelector('.ejs_virtualGamepad_button.b_a');
        const r=button.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;
        return {x,y,w:innerWidth,h:innerHeight,target:document.elementFromPoint(x,y)?.className};
      })())''') as Map;
      final finder = find.byType(WebViewWidget);
      final size = tester.getSize(finder), origin = tester.getTopLeft(finder);
      touchButton = await tester.startGesture(origin +
          Offset(
              (rect['x'] as num).toDouble() * size.width / (rect['w'] as num),
              (rect['y'] as num).toDouble() *
                  size.height /
                  (rect['h'] as num)));
    } else {
      await touchButton?.up();
      touchButton = null;
    }
  } else {
    await evaluate(tester, '''EJS_emulator.elements.parent.focus();
    EJS_emulator.elements.parent.dispatchEvent(new KeyboardEvent('${pressed ? 'keydown' : 'keyup'}',
      {key:'z',code:'KeyZ',keyCode:90,which:90,bubbles:true}));''');
  }
  await Future<void>.delayed(const Duration(milliseconds: 700));
  await tester.pump(const Duration(milliseconds: 500));
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('motores reales integrados: NDS y clásicos, controles y guardado',
      (tester) async {
    const configured = String.fromEnvironment('PLAYER_TEST_SERVER');
    final base = configured.isNotEmpty
        ? configured
        : Platform.isAndroid
            ? 'http://10.0.2.2:8687'
            : 'http://127.0.0.1:8687';
    final api = GameClubApi(base, '');
    final games = await api.list('/api/games');
    const outputPath = String.fromEnvironment('PLAYER_TEST_OUTPUT');
    final root = Directory(outputPath.isNotEmpty
        ? outputPath
        : p.join((await getTemporaryDirectory()).path, 'gameclub-player-test'));
    await root.create(recursive: true);
    final host = PlayerHost(Directory(p.join(root.path, 'host')));
    await host.start();
    addTearDown(() async {
      await host.close();
      api.dio.close();
    });
    const requestedSystems = String.fromEnvironment('PLAYER_TEST_SYSTEMS',
        defaultValue: 'nds,gb,gba,gbc,snes');
    for (final system in requestedSystems.split(',')) {
      final game = games.firstWhere((g) => g['system_id'] == system);
      final rom = File(p.join(root.path, game['filename'] as String));
      await api.dio.download('/api/games/${game['id']}/download', rom.path);
      const ndsMode = String.fromEnvironment('PLAYER_TEST_PROFILE',
          defaultValue: 'balanced');
      final uri = host.open(game, rom, api,
          mobile: Platform.isAndroid, ndsProfile: ndsMode);
      await tester.pumpWidget(MaterialApp(
          home: Builder(
              builder: (context) => Scaffold(
                    body: Center(
                        child: FilledButton(
                            onPressed: () => Navigator.of(context).push(
                                MaterialPageRoute<void>(
                                    builder: (_) => IntegratedPlayer(
                                        uri: uri, title: system))),
                            child: const Text('Abrir prueba'))),
                  ))));
      Future<void> open() async {
        await tester.tap(find.text('Abrir prueba'));
        await until(
            tester,
            () async => (Platform.isWindows
                    ? find.byType(Webview)
                    : find.byType(WebViewWidget))
                .evaluate()
                .isNotEmpty);
        await evaluate(
            tester, '''window.__warnings=[]; const originalWarn=console.warn;
          console.warn=(...values)=>{window.__warnings.push(values.map(v=>v && v.stack ? v.stack : String(v)).join(' '));originalWarn(...values);};
          window.addEventListener('unhandledrejection',e=>window.__warnings.push(e.reason && e.reason.stack ? e.reason.stack : String(e.reason)));''');
        await until(tester, () async {
          if (await evaluate(tester,
                  "!!(window.EJS_emulator && EJS_emulator.failedToStart) || document.body.innerText.includes('Error al iniciar el juego')") ==
              true) {
            throw StateError(
                (await evaluate(tester, "JSON.stringify(window.__warnings)"))
                    .toString());
          }
          return await evaluate(tester,
                  '!!(window.EJS_emulator && EJS_emulator.started && EJS_emulator.gameManager && EJS_emulator.gameManager.functions.getFrameNum() > 45)') ==
              true;
        });
      }

      Future<void> close() async {
        await tester.tap(find.byTooltip('Menú del juego'));
        await until(tester,
            () async => find.text('Menú del juego').evaluate().isNotEmpty);
        await tester.tap(find.text('Guardar y volver a la biblioteca'));
        await until(tester,
            () async => find.text('Abrir prueba').evaluate().isNotEmpty);
      }

      await open();
      expect(
          await evaluate(tester,
              'typeof navigator.getGamepads === "function" && window.isSecureContext'),
          isTrue,
          reason: 'El contexto no ofrece la API de mandos');
      final before =
          await snapshot(tester, File(p.join(root.path, '$system-before.png')));
      expect(before.width, greaterThanOrEqualTo(128));
      if (system != 'gb') {
        final red = before
            .where((pixel) =>
                pixel.r > 160 &&
                pixel.r > pixel.g * 1.5 &&
                pixel.r > pixel.b * 1.5)
            .length;
        expect(red, greaterThan(before.width * before.height ~/ 10),
            reason: '$system no ejecutó el programa gráfico');
      }
      await pressA(tester, true);
      final after =
          await snapshot(tester, File(p.join(root.path, '$system-after.png')));
      expect(before.getBytes(), isNot(equals(after.getBytes())),
          reason: '$system no respondió al botón A');
      await pressA(tester, false);
      if (system == 'nds' && Platform.isAndroid) {
        final rect = await evaluate(tester, '''JSON.stringify((() => {
          const r=EJS_emulator.canvas.getBoundingClientRect();
          const x=r.x+r.width/2,y=r.y+r.height*0.75;
          return {x,y,w:innerWidth,h:innerHeight,target:document.elementFromPoint(x,y)?.className};
        })())''') as Map;
        final finder = find.byType(WebViewWidget);
        final size = tester.getSize(finder), origin = tester.getTopLeft(finder);
        final pen = await tester.startGesture(origin +
            Offset(
                (rect['x'] as num).toDouble() * size.width / (rect['w'] as num),
                (rect['y'] as num).toDouble() *
                    size.height /
                    (rect['h'] as num)));
        await tester.pump(const Duration(milliseconds: 800));
        final touched =
            await snapshot(tester, File(p.join(root.path, 'nds-touch.png')));
        await pen.up();
        final blue = touched
            .where((pixel) => pixel.b > 160 && pixel.b > pixel.r * 1.5)
            .length;
        expect(blue, greaterThan(touched.width * touched.height ~/ 10),
            reason: 'La pantalla táctil NDS no recibió el lápiz');
        await Future<void>.delayed(const Duration(milliseconds: 500));
        final released =
            await snapshot(tester, File(p.join(root.path, 'nds-release.png')));
        expect(
            released
                .where((pixel) => pixel.b > 160 && pixel.b > pixel.r * 1.5)
                .length,
            0,
            reason: 'El lápiz NDS quedó pulsado después de levantar el dedo');
        debugPrint('Pantalla táctil NDS: OK');
      }
      dynamic saved;
      if (system == 'gb') {
        saved =
            await evaluate(tester, 'EJS_emulator.gameManager.getSaveFile()[0]');
      }
      await close();
      if (system == 'gb') {
        await open();
        final restored =
            await evaluate(tester, 'EJS_emulator.gameManager.getSaveFile()[0]');
        expect(restored, ((saved as num).toInt() + 1) & 255,
            reason: 'La SRAM no se conservó al cerrar');
        await close();
      }
      host.release(uri);
      debugPrint(
          'Motor $system, vídeo, botón A${system == 'gb' ? ' y SRAM persistente' : ''}: OK');
    }
    await tester.pumpWidget(const SizedBox.shrink());
  }, timeout: const Timeout(Duration(minutes: 12)));
}
