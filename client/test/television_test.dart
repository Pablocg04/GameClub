import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/main.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/television.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'library_test.dart' show LibraryAdapter;

class TelevisionAdapter extends LibraryAdapter {
  @override
  Future<ResponseBody> fetch(
      RequestOptions request, Stream<Uint8List>? stream, Future<void>? cancel) {
    if (request.path == '/api/games') {
      requests.add(request);
      return Future.value(ResponseBody.fromString(
          jsonEncode(List.generate(
              80,
              (index) => {
                    'id': 'tv$index',
                    'title': 'Juego TV $index',
                    'filename': '$index.gba',
                    'system_id': 'gba',
                    'size': 1024,
                    'favorite': false,
                    'cover_url': null,
                    'description': ''
                  })),
          200,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType]
          }));
    }
    if (request.path.endsWith('/screenshots')) {
      return Future.value(ResponseBody.fromString(
          '{"images":[],"checked":true}', 200,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType]
          }));
    }
    return super.fetch(request, stream, cancel);
  }
}

class ManySystemsAdapter extends TelevisionAdapter {
  @override
  Future<ResponseBody> fetch(
      RequestOptions request, Stream<Uint8List>? stream, Future<void>? cancel) {
    if (request.path == '/api/systems') {
      requests.add(request);
      return Future.value(ResponseBody.fromString(
          jsonEncode(List.generate(
              16,
              (index) => {
                    'id': 'sys$index',
                    'name': 'Sistema largo $index',
                    'game_count': 1,
                    'extensions': ['.zip'],
                    'emulator': 'Native'
                  })),
          200,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType]
          }));
    }
    return super.fetch(request, stream, cancel);
  }
}

void main() {
  testWidgets(
      'TV: recorre filtros fuera de pantalla, selecciona con A y baja a juegos',
      (tester) async {
    tester.view.physicalSize = const Size(962, 541);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    final adapter = ManySystemsAdapter();
    api.dio.httpClientAdapter = adapter;
    await tester.pumpWidget(GameClubApp(apiOverride: api, television: true));
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowUp);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Filtro TV');
    for (var i = 0; i < 12; i++) {
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
      await tester.pumpAndSettle();
    }
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Filtro TV 12');
    final chip = find.widgetWithText(ChoiceChip, 'Sistema largo 11 · 1');
    final row = find.byType(TelevisionFilters);
    expect(tester.getRect(chip).right,
        lessThanOrEqualTo(tester.getRect(row).right + 1));
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonA);
    await tester.pumpAndSettle();
    expect(
        adapter.requests.any((request) =>
            request.path == '/api/games' &&
            request.queryParameters['system_id'] == 'sys11'),
        true);
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Juego TV 0');
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('TV: baja por campos y operaciones de ajustes hasta Nintendo DS',
      (tester) async {
    tester.view.physicalSize = const Size(962, 541);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    api.dio.httpClientAdapter = TelevisionAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api, television: true));
    await tester.pumpAndSettle();
    for (var i = 0; i < 2; i++) {
      await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonRight1);
      await tester.pumpAndSettle();
    }
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowUp);
    await tester.pumpAndSettle();
    var server = false, nds = false;
    for (var i = 0; i < 50; i++) {
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
      await tester.pumpAndSettle();
      server |= FocusManager.instance.primaryFocus?.debugLabel == 'Servidor TV';
      final dropdown = FocusManager.instance.primaryFocus?.context
          ?.findAncestorWidgetOfExactType<DropdownButtonFormField<String>>();
      if (dropdown?.decoration.labelText == 'Rendimiento de Nintendo DS') {
        nds = true;
        break;
      }
    }
    expect(server, true);
    expect(nds, true);
    final settings = find.byType(TelevisionSettings);
    final target = find.byWidgetPredicate((widget) =>
        widget is DropdownButtonFormField<String> &&
        widget.decoration.labelText == 'Rendimiento de Nintendo DS');
    expect(tester.getRect(target).bottom,
        lessThanOrEqualTo(tester.getRect(settings).bottom + 1));
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('móvil: guarda orientación vertical y tamaño táctil',
      (tester) async {
    final info = DevicePlatform.info;
    DevicePlatform.info = {'variant': 'mobile'};
    addTearDown(() {
      DevicePlatform.info = info;
      DevicePlatform.mobileOrientation = 'auto';
      DevicePlatform.touchScale = 1;
    });
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    api.dio.httpClientAdapter = TelevisionAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ajustes'));
    await tester.pumpAndSettle();
    expect(find.text('Pantalla y controles del móvil'), findsOneWidget);
    expect(find.text('Rendimiento rápido para TV'), findsNothing);
    await tester.tap(find.text('Automática (girar el móvil)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Vertical').last);
    await tester.pumpAndSettle();
    expect(DevicePlatform.mobileOrientation, 'portrait');
    expect(
        (await SharedPreferences.getInstance()).getString('mobileOrientation'),
        'portrait');
    await tester.drag(find.byType(Slider), const Offset(70, 0));
    await tester.pumpAndSettle();
    expect(DevicePlatform.touchScale, greaterThan(1));
    expect((await SharedPreferences.getInstance()).getDouble('touchScale'),
        DevicePlatform.touchScale);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('móvil: conectar un mando activa foco y navegación sin reiniciar',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    DevicePlatform.gamepadConnected.value = false;
    addTearDown(() => DevicePlatform.gamepadConnected.value = false);
    final api = GameClubApi('http://test', '');
    api.dio.httpClientAdapter = TelevisionAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationBar), findsOneWidget);
    DevicePlatform.gamepadConnected.value = true;
    await tester.pumpAndSettle();
    expect(find.byType(TelevisionGrid), findsOneWidget);
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonRight1);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV 1');
    DevicePlatform.gamepadConnected.value = false;
    await tester.pumpAndSettle();
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets(
      'TV: LB/RB cambia pestañas y Select enfoca búsqueda y abre teclado',
      (tester) async {
    tester.view.physicalSize = const Size(962, 541);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    final adapter = TelevisionAdapter();
    api.dio.httpClientAdapter = adapter;
    await tester.pumpWidget(GameClubApp(apiOverride: api, television: true));
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonRight1);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV 1');
    expect(
        adapter.requests.any((request) =>
            request.path == '/api/games' &&
            request.queryParameters['favorites'] == true),
        true);
    for (final tab in [2, 0]) {
      await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonRight1);
      await tester.pumpAndSettle();
      expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV $tab');
    }
    tester.testTextInput.log.clear();
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonSelect);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Buscar TV');
    expect(
        tester.testTextInput.log.any((call) => call.method == 'TextInput.show'),
        true);
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonLeft1);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV 2');
    tester.testTextInput.log.clear();
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonSelect);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV 2');
    expect(
        tester.testTextInput.log.any((call) => call.method == 'TextInput.show'),
        false);
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonLeft1);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV 1');
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonSelect);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Buscar TV');
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
    await tester.pumpAndSettle();
    // Una ficha abierta conserva sus entradas: los atajos de biblioteca no la cambian.
    await tester.tap(find.text('Juego TV 0'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsOneWidget);
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonRight1);
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsOneWidget);
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonB);
    await tester.pumpAndSettle();
    expect(find.text('Rendimiento rápido para TV'), findsNothing);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('TV: desde juegos se accede a Favoritos y Ajustes sin tacto',
      (tester) async {
    tester.view.physicalSize = const Size(962, 541);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    final adapter = TelevisionAdapter();
    api.dio.httpClientAdapter = adapter;
    await tester.pumpWidget(GameClubApp(apiOverride: api, television: true));
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowLeft);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV 0');
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonA);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV 1');
    expect(
        adapter.requests.any((r) =>
            r.path == '/api/games' && r.queryParameters['favorites'] == true),
        true);
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonA);
    await tester.pumpAndSettle();
    expect(find.text('Rendimiento rápido para TV'), findsOneWidget);
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV 2');
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowUp);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Rendimiento TV');
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonA);
    await tester.pumpAndSettle();
    expect((await SharedPreferences.getInstance()).getBool('fastTelevision'),
        false);
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonB);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú TV 2');
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets(
      'Android TV: cruceta desplaza la cuadrícula, A abre ficha y B vuelve',
      (tester) async {
    tester.view.physicalSize = const Size(962, 541);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    api.dio.httpClientAdapter = TelevisionAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api, television: true));
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Juego TV 0');
    expect(tester.getRect(find.text('Juego TV 0')).bottom,
        lessThanOrEqualTo(tester.getRect(find.byType(TelevisionGrid)).bottom));
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Juego TV 1');
    for (var row = 0; row < 5; row++) {
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
      await tester.pumpAndSettle();
    }
    final selected = FocusManager.instance.primaryFocus?.debugLabel;
    expect(selected, isNot('Juego TV 1'));
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonA);
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsOneWidget);
    expect(find.text('Capturas del juego'), findsOneWidget);
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonB);
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
    expect(FocusManager.instance.primaryFocus?.debugLabel, selected);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
