import 'dart:async';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/android_gamepad.dart';
import 'package:gameclub/television.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('cerrar espera la liberación nativa antes de cancelar y es idempotente',
      () async {
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    final released = Completer<void>();
    final calls = <String>[];
    final owners = <String>[];
    messenger.setMockMethodCallHandler(DevicePlatform.channel, (call) async {
      final arguments = Map<String, dynamic>.from(call.arguments as Map);
      owners.add(arguments['owner'] as String);
      calls.add(arguments['active'] == true ? 'active' : 'release');
      if (arguments['active'] == false) {
        expect(arguments['restoreDisplay'], true);
        await released.future;
      }
      return null;
    });
    messenger.setMockMethodCallHandler(const MethodChannel('gameclub/gamepad'),
        (call) async {
      calls.add(call.method);
      return null;
    });
    addTearDown(() {
      messenger.setMockMethodCallHandler(DevicePlatform.channel, null);
      messenger.setMockMethodCallHandler(
          const MethodChannel('gameclub/gamepad'), null);
    });
    final bridge = AndroidGamepad(execute: (_) async {}, onMenu: () {});
    await bridge.start();
    await Future<void>.delayed(Duration.zero);
    final stop = bridge.dispose();
    expect(identical(stop, bridge.dispose()), true);
    await Future<void>.delayed(Duration.zero);
    expect(calls, isNot(contains('cancel')));
    await bridge.active(true);
    expect(calls.where((call) => call == 'active'), hasLength(1));
    released.complete();
    await stop;
    expect(calls.indexOf('cancel'), greaterThan(calls.indexOf('release')));
    expect(owners, everyElement(bridge.owner));
  });
  test('desconectar libera el mando y el menú descarta ejes pendientes',
      () async {
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(
        DevicePlatform.channel, (_) async => null);
    messenger.setMockMethodCallHandler(
        const MethodChannel('gameclub/gamepad'), (_) async => null);
    Future<void> emit(Map<String, dynamic> event) async {
      final completed = Completer<void>();
      await messenger.handlePlatformMessage(
          'gameclub/gamepad',
          const StandardMethodCodec().encodeSuccessEnvelope(event),
          (_) => completed.complete());
      await completed.future;
    }

    final scripts = <String>[];
    var menus = 0;
    final bridge = AndroidGamepad(
        execute: (script) async {
          scripts.add(script);
        },
        onMenu: () => menus++);
    await bridge.start();
    await Future<void>.delayed(Duration.zero);
    await emit({
      'type': 'axes',
      'device': 4,
      'axes': [1, 0, 0, 0, 0, 0, 0, 0]
    });
    await emit({'type': 'disconnect', 'device': 4});
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(scripts.single, contains('disconnect'));
    expect(scripts.single, isNot(contains('"type":"axes"')));
    scripts.clear();
    await emit({
      'type': 'axes',
      'device': 4,
      'axes': [1, 0, 0, 0, 0, 0, 0, 0]
    });
    await emit({'type': 'menu'});
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(menus, 1);
    expect(scripts, isEmpty);
    await bridge.dispose();
    messenger.setMockMethodCallHandler(DevicePlatform.channel, null);
    messenger.setMockMethodCallHandler(
        const MethodChannel('gameclub/gamepad'), null);
  }, timeout: const Timeout(Duration(seconds: 20)));
}
