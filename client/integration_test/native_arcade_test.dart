import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/main.dart';
import 'package:gameclub/native_arcade.dart';
import 'package:gameclub/native_console.dart';
import 'package:gameclub/television.dart';
import 'package:image/image.dart' as image;
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

Future<void> waitNative(Future<bool> Function() predicate,
    {Duration timeout = const Duration(minutes: 3)}) async {
  final end = DateTime.now().add(timeout);
  while (DateTime.now().isBefore(end)) {
    if (await predicate()) return;
    // Flutter no produce frames mientras la actividad SDL está delante.
    await Future<void>.delayed(const Duration(milliseconds: 200));
  }
  throw StateError('Tiempo agotado esperando el motor nativo');
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Nativo: vídeo, controles, menú, salida y segundo arranque',
      (tester) async {
    await DevicePlatform.initialize();
    const variant =
        String.fromEnvironment('NATIVE_TEST_VARIANT', defaultValue: 'tv');
    expect(DevicePlatform.television, variant == 'tv');
    final api = GameClubApi(
        const String.fromEnvironment('NATIVE_TEST_SERVER',
            defaultValue: 'http://192.168.0.47:8001'),
        '');
    const filename = String.fromEnvironment('NATIVE_TEST_GAME',
        defaultValue: 'arkanoid.zip');
    const system =
        String.fromEnvironment('NATIVE_TEST_SYSTEM', defaultValue: 'mame');
    final game = (await api.list('/api/games')).firstWhere(
        (game) => game['system_id'] == system && game['filename'] == filename);
    final library =
        api.dio.options.baseUrl.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_');
    final saves = Directory(p.join(
        (await getApplicationSupportDirectory()).path,
        'native',
        'saves',
        library,
        game['id'] as String));
    Future<File?> current(String state) async {
      if (!await saves.exists()) return null;
      await for (final entity in saves.list(recursive: true)) {
        if (entity is File && p.basename(entity.path) == 'session.txt') {
          final text = await entity.readAsString();
          if (text.startsWith('$state\n')) return entity;
        }
      }
      return null;
    }

    await tester.pumpWidget(GameClubApp(apiOverride: api));
    await tester.pump(const Duration(seconds: 2));
    DevicePlatform.mobileOrientation = const String.fromEnvironment(
        'NATIVE_TEST_ORIENTATION',
        defaultValue: 'auto');
    if (await saves.exists()) {
      await for (final entity in saves.list(recursive: true)) {
        if (entity is File &&
            {'session.txt', 'session.txt.bmp'}
                .contains(p.basename(entity.path))) {
          await entity.delete();
        }
      }
    }
    final launcher = NativeArcade(api);
    Object? failure;
    Future<void> launch() async {
      try {
        if (nativeConsoleCores.containsKey(system)) {
          await NativeConsole(api).play(game,
              touchControls: const bool.fromEnvironment('NATIVE_TEST_TOUCH'),
              diagnostics: true);
        } else {
          await launcher.play(game,
              touchControls: const bool.fromEnvironment('NATIVE_TEST_TOUCH'),
              diagnostics: true);
        }
      } catch (error) {
        failure = error;
      }
    }

    var completed = launch();
    Future<void> running() => waitNative(() async {
          if (failure != null) throw StateError('$failure');
          final file = await current('running');
          if (file == null) return false;
          final lines = await file.readAsLines();
          return lines.length > 1 && (double.tryParse(lines[1]) ?? 0) > 0;
        }, timeout: const Duration(minutes: 8));
    await running();
    final report = (await current('running'))!;
    if (const bool.fromEnvironment('NATIVE_TEST_ROTATE')) {
      debugPrint('NATIVE_PREPARE_PORTRAIT_READY');
      await waitNative(() async {
        try {
          final state =
              jsonDecode(await File('${report.path}.layout').readAsString())
                  as Map;
          return (state['height'] as num) > (state['width'] as num);
        } catch (_) {
          return false;
        }
      });
    }
    debugPrint(
        'NATIVE_VIDEO $filename ${report.parent.path} ${await report.readAsString()}');
    await waitNative(() async => File('${report.path}.bmp').exists());
    debugPrint('NATIVE_CAPTURE_READY ${report.path}.bmp');
    await Future<void>.delayed(const Duration(seconds: 2));
    final frame =
        image.decodeBmp(await File('${report.path}.bmp').readAsBytes())!;
    final layout =
        jsonDecode(await File('${report.path}.layout').readAsString()) as Map;
    void checkControlImage(image.Image photo, Map geometry) {
      expect(photo.width, geometry['width']);
      expect(photo.height, geometry['height']);
      if (const bool.fromEnvironment('NATIVE_TEST_TOUCH')) {
        final button = (geometry['buttons'] as List)
            .cast<Map>()
            .firstWhere((button) => button['index'] == 8);
        final pixel = photo.getPixel(
            ((button['x'] as num) + (button['w'] as num) * .3).round(),
            (button['y'] as num).round());
        expect(pixel.r, greaterThan(40),
            reason: 'La imagen del botón no coincide con su área táctil');
        expect((pixel.r - pixel.g).abs(), lessThan(20));
      }
    }

    checkControlImage(frame, layout);
    if (variant == 'mobile' &&
        (DevicePlatform.mobileOrientation == 'portrait' ||
            const bool.fromEnvironment('NATIVE_TEST_ROTATE'))) {
      expect(frame.height, greaterThan(frame.width));
      expect(layout['portrait'], true);
      expect((layout['diameter'] as num) / (layout['density'] as num),
          greaterThan(55));
    }
    expect(frame.width, greaterThan(200));
    final colors = <int>{};
    final videoHeight = (layout['videoHeight'] as num).toInt();
    for (var y = videoHeight ~/ 4; y < videoHeight * 3 ~/ 4; y += 3) {
      for (var x = frame.width ~/ 4; x < frame.width * 3 ~/ 4; x += 3) {
        final pixel = frame.getPixel(x, y);
        colors.add(
            (pixel.r.toInt() << 16) | (pixel.g.toInt() << 8) | pixel.b.toInt());
      }
    }
    expect(colors.length, greaterThan(2));
    debugPrint('NATIVE_INPUT_READY');
    await waitNative(() async {
      final file = await current('running');
      if (file == null) return false;
      final text = await file.readAsString();
      final match = RegExp(r'inputs=([0-9]+)').firstMatch(text);
      final consumed = RegExp(r'consumed=([0-9]+)').firstMatch(text);
      return match != null &&
          int.parse(match.group(1)!) >= 3 &&
          consumed != null &&
          int.parse(consumed.group(1)!) > 0;
    });
    if (!const bool.fromEnvironment('NATIVE_TEST_TOUCH')) {
      int count(String text, String key) =>
          int.tryParse(
              RegExp('$key=([0-9]+)').firstMatch(text)?.group(1) ?? '0') ??
          0;
      await waitNative(
          () async => count(await report.readAsString(), 'directions') > 0);
      final beforeAxes = count(await report.readAsString(), 'directions');
      debugPrint('NATIVE_AXIS_READY');
      await waitNative(() async {
        final state = await report.readAsString();
        return count(state, 'axis_packets') > 0 &&
            count(state, 'directions') > beforeAxes;
      });
    }
    if (nativeConsoleCores.containsKey(system)) {
      await waitNative(() async {
        final state = await report.readAsString();
        return (int.tryParse(RegExp(r'audio_signals=([0-9]+)')
                        .firstMatch(state)
                        ?.group(1) ??
                    '0') ??
                0) >
            10;
      });
    }
    debugPrint('NATIVE_MENU_READY');
    await waitNative(() async => await current('menu') != null);
    debugPrint('NATIVE_RESUME_READY');
    await running();
    if (const bool.fromEnvironment('NATIVE_TEST_ROTATE')) {
      debugPrint('NATIVE_ROTATE_READY');
      await waitNative(() async {
        try {
          final state =
              jsonDecode(await File('${report.path}.layout').readAsString())
                  as Map;
          return (state['width'] as num) > (state['height'] as num);
        } catch (_) {
          return false;
        }
      });
      await waitNative(() async {
        try {
          final photo =
              image.decodeBmp(await File('${report.path}.bmp').readAsBytes());
          return photo != null && photo.width > photo.height;
        } catch (_) {
          return false;
        }
      });
      debugPrint('NATIVE_ROTATED_CAPTURE_READY ${report.path}.bmp');
      await Future<void>.delayed(const Duration(seconds: 2));
      final rotatedLayout =
          jsonDecode(await File('${report.path}.layout').readAsString()) as Map;
      checkControlImage(
          image.decodeBmp(await File('${report.path}.bmp').readAsBytes())!,
          rotatedLayout);
    }
    debugPrint('NATIVE_EXIT_READY');
    await waitNative(() async => await current('menu') != null);
    debugPrint('NATIVE_CONFIRM_EXIT_READY');
    await waitNative(() async => await current('closed') != null);
    await completed.timeout(const Duration(seconds: 20));
    expect(failure, isNull);
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.byType(AlertDialog), findsNothing);
    if (Platform.isAndroid) {
      expect(
          (await DevicePlatform.channel
              .invokeMapMethod<String, dynamic>('info'))?['playerActive'],
          false);
    }
    await Future<void>.delayed(const Duration(seconds: 1));
    completed = launch();
    await running();
    debugPrint('NATIVE_SECOND_EXIT_READY');
    await waitNative(() async => await current('menu') != null);
    debugPrint('NATIVE_SECOND_CONFIRM_EXIT_READY');
    await waitNative(() async => await current('closed') != null);
    await completed;
    expect(failure, isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  }, timeout: const Timeout(Duration(minutes: 15)));
}
