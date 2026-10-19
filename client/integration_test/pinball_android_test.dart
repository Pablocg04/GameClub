import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/pinball_player.dart';
import 'package:gameclub/television.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Android sin VPX informa el requisito antes de descargar',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    final capabilities = await DevicePlatform.channel
        .invokeMapMethod<String, dynamic>('pinballCapabilities');
    debugPrint('PINBALL_ANDROID_CAPABILITIES $capabilities');
    expect(capabilities!['compatible'], isA<bool>());
    expect(capabilities['installed'], isFalse);
    final reason = capabilities['compatible'] == true
        ? 'Instala Visual Pinball oficial'
        : 'ARM64';
    // Sin servidor: el error debe producirse antes de cualquier petición HTTP.
    await expectLater(
        PinballPlayer(GameClubApi('http://127.0.0.1:1', '')).play({}),
        throwsA(predicate((error) => error.toString().contains(reason))));
  });
  testWidgets('el puente rechaza compartir archivos fuera de pinball-share',
      (tester) async {
    await expectLater(
        DevicePlatform.channel.invokeMethod<void>(
            'openPinball', {'path': '/sdcard/Download/foreign.vpxz'}),
        throwsA(isA<PlatformException>()
            .having((error) => error.code, 'code', 'pinball')));
  });
  testWidgets('FileProvider entrega un VPXZ válido hasta la búsqueda de VPX',
      (tester) async {
    final capabilities = await DevicePlatform.channel
        .invokeMapMethod<String, dynamic>('pinballCapabilities');
    expect(capabilities!['installed'], isFalse);
    final temporary = await getTemporaryDirectory();
    final file =
        File(p.join(temporary.path, 'pinball-share', 'provider-test.vpxz'));
    await file.parent.create(recursive: true);
    await file.writeAsBytes([0x50, 0x4b, 0x05, 0x06, ...List.filled(18, 0)]);
    addTearDown(() => file.delete());
    await expectLater(
        DevicePlatform.channel
            .invokeMethod<void>('openPinball', {'path': file.path}),
        throwsA(isA<PlatformException>().having((error) => error.message,
            'message', contains('Instala Visual Pinball oficial'))));
  });
}
