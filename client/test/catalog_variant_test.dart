import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/main.dart';
import 'package:gameclub/television.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'library_test.dart' show BatchPicker, LibraryAdapter;

class MixedPinballAdapter extends LibraryAdapter {
  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? stream,
      Future<void>? cancel) async {
    Object? data;
    if (options.path == '/api/systems') {
      data = [
        {
          'id': 'gba',
          'name': 'Game Boy Advance',
          'game_count': 1,
          'extensions': ['.gba', '.zip'],
          'emulator': 'mGBA'
        },
        {
          'id': 'mame',
          'name': 'Arcade · MAME',
          'game_count': 1,
          'extensions': ['.zip'],
          'emulator': 'MAME'
        },
        {
          'id': 'vpinball',
          'name': 'Visual Pinball · PinMAME',
          'game_count': 1,
          'extensions': ['.zip', '.vpx'],
          'emulator': 'VPX'
        },
      ];
    } else if (options.path == '/api/games') {
      // El servidor comparte las mismas mesas con todos los dispositivos.
      data = [
        for (final item in [
          ('gba', 'Consola portátil'),
          ('mame', 'Pinball Action'),
          ('vpinball', 'Attack from Mars')
        ])
          {
            'id': item.$1,
            'system_id': item.$1,
            'title': item.$2,
            'filename': '${item.$1}.zip',
            'size': 1024,
            'favorite': true,
            'cover_url': null,
            'description': ''
          }
      ];
    }
    if (data == null) return super.fetch(options, stream, cancel);
    requests.add(options);
    return ResponseBody.fromString(jsonEncode(data), 200, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType]
    });
  }
}

void main() {
  setUp(() => FilePicker.platform = BatchPicker([]));
  testWidgets('APK TV oculta VPX en biblioteca, favoritos, vacías y subida',
      (tester) async {
    final originalInfo = DevicePlatform.info;
    final originalPicker = FilePicker.platform;
    DevicePlatform.info = {'variant': 'tv'};
    addTearDown(() {
      DevicePlatform.info = originalInfo;
      FilePicker.platform = originalPicker;
    });
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    api.dio.httpClientAdapter = MixedPinballAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api, television: true));
    await tester.pumpAndSettle();
    expect(find.text('Attack from Mars'), findsNothing);
    expect(find.textContaining('Visual Pinball'), findsNothing);
    expect(find.text('Pinball Action'), findsOneWidget);

    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonRight1);
    await tester.pumpAndSettle();
    expect(find.text('Attack from Mars'), findsNothing);
    expect(find.text('Pinball Action'), findsOneWidget);
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonRight1);
    await tester.pumpAndSettle();
    final empty = find.text('Mostrar consolas vacías');
    await tester.ensureVisible(empty);
    await tester.tap(empty);
    await tester.pumpAndSettle();
    expect(find.textContaining('Visual Pinball'), findsNothing);

    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonRight1);
    await tester.pumpAndSettle();
    expect(find.textContaining('Visual Pinball'), findsNothing);
    expect(find.text('Pinball Action'), findsOneWidget);
    FilePicker.platform = BatchPicker(
        [PlatformFile(name: 'Mesa.zip', size: 10, path: 'C:/tests/Mesa.zip')]);
    await tester.tap(find.byTooltip('Añadir juego'));
    await tester.pumpAndSettle();
    final dropdown = tester
        .widget<DropdownButton<String>>(find.byType(DropdownButton<String>));
    expect(dropdown.items!.any((item) => item.value == 'vpinball'), isFalse);
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
      'móvil con mando mantiene Visual Pinball aunque use navegación TV',
      (tester) async {
    final originalInfo = DevicePlatform.info;
    final connected = DevicePlatform.gamepadConnected.value;
    DevicePlatform.info = {'variant': 'mobile'};
    DevicePlatform.gamepadConnected.value = true;
    addTearDown(() {
      DevicePlatform.info = originalInfo;
      DevicePlatform.gamepadConnected.value = connected;
    });
    SharedPreferences.setMockInitialValues({});
    final api = GameClubApi('http://test', '');
    api.dio.httpClientAdapter = MixedPinballAdapter();
    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pumpAndSettle();
    expect(find.text('Attack from Mars'), findsOneWidget);
    expect(find.textContaining('Visual Pinball'), findsOneWidget);
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonRight1);
    await tester.pumpAndSettle();
    expect(find.text('Attack from Mars'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
