import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/main.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'library_test.dart' show LibraryAdapter;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final font = FontLoader('PressStart2P')
      ..addFont(rootBundle.load('assets/fonts/PressStart2P-Regular.ttf'));
    await font.load();
  });

  testWidgets('al girar conserva búsqueda y títulos con las barras del móvil',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    tester.view.padding = const FakeViewPadding(top: 24, bottom: 24);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPadding);
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '')
      ..dio.httpClientAdapter = LibraryAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('library-search')), 'Mi');
    tester.view.physicalSize = const Size(844, 390);
    await tester.pumpAndSettle();
    expect(
        tester
            .widget<TextField>(find.byKey(const ValueKey('library-search')))
            .controller!
            .text,
        'Mi');
    final grid = find.byType(GridView);
    final card = find.byKey(const ValueKey('game-test'));
    expect(tester.getRect(card).bottom,
        lessThanOrEqualTo(tester.getRect(grid).bottom + 1));
    await tester.tap(find.text('Mi juego'));
    await tester.pumpAndSettle();
    expect(find.text('Capturas del juego'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  for (final screen in [
    ('phone-small', const Size(320, 568), false, 1.0),
    ('phone', const Size(390, 844), false, 1.0),
    ('landscape', const Size(844, 390), false, 1.0),
    ('desktop', const Size(1440, 1000), false, 1.0),
    ('tv', const Size(962, 541), true, 1.0),
    ('phone-controller', const Size(390, 844), true, 1.0),
    ('large-text', const Size(390, 844), false, 1.5),
  ]) {
    testWidgets('biblioteca retro: ${screen.$1}, ficha y pestañas accesibles',
        (tester) async {
      tester.view.physicalSize = screen.$2;
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.textScaleFactorTestValue = screen.$4;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      SharedPreferences.setMockInitialValues({});
      final api = GameClubApi('http://test', '')
        ..dio.httpClientAdapter = LibraryAdapter();
      final boundary = GlobalKey();
      await tester.pumpWidget(RepaintBoundary(
          key: boundary,
          child: GameClubApp(apiOverride: api, television: screen.$3)));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      final grid = find.byType(GridView);
      final card = find.byKey(const ValueKey('game-test'));
      expect(tester.getRect(card).bottom,
          lessThanOrEqualTo(tester.getRect(grid).bottom + 1));
      if (Platform.environment['GAMECLUB_CAPTURE_UI'] == '1') {
        await tester.runAsync(() async {
          final render = boundary.currentContext!.findRenderObject()!
              as RenderRepaintBoundary;
          final image = await render.toImage();
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          final folder = Directory('../dist/retro-previews')
            ..createSync(recursive: true);
          File('${folder.path}/${screen.$1}.png')
              .writeAsBytesSync(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }
      await tester.tap(find.text('Mi juego'));
      await tester.pumpAndSettle();
      expect(find.text('Capturas del juego'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.tapAt(const Offset(4, 4));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Favoritos'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Tus clásicos favoritos'), findsOneWidget);
      await tester.tap(find.text('Ajustes'));
      await tester.pumpAndSettle();
      expect(find.text('Conexión con tu Raspberry'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    });
  }
}
