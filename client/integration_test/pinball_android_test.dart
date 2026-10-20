import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/pinball_player.dart';
import 'package:gameclub/television.dart';
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Android ofrece el motor incluido sin consultar otra aplicación',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    final capabilities = await DevicePlatform.channel
        .invokeMapMethod<String, dynamic>('pinballCapabilities');
    debugPrint('PINBALL_ANDROID_CAPABILITIES $capabilities');
    expect(capabilities!['compatible'], isA<bool>());
    expect(capabilities['integrated'], isTrue);
    expect(capabilities.containsKey('installed'), isFalse);
  });
  testWidgets('un Android incompatible falla antes de descargar la mesa',
      (tester) async {
    final capabilities = await DevicePlatform.channel
        .invokeMapMethod<String, dynamic>('pinballCapabilities');
    if (capabilities!['compatible'] == true) {
      expect(capabilities['reason'], isEmpty);
      return;
    }
    await expectLater(
        PinballPlayer(GameClubApi('http://127.0.0.1:1', '')).play({}),
        throwsA(predicate((error) =>
            error.toString().contains(capabilities['reason'] as String))));
  });
  testWidgets('el motor no permite abrir mesas o guardados fuera de GameClub',
      (tester) async {
    await expectLater(
        DevicePlatform.channel.invokeMethod<void>('playPinball', {
          'path': '/sdcard/Download/foreign.vpx',
          'preferences': '/sdcard/Download/saves',
        }),
        throwsA(isA<PlatformException>()
            .having((error) => error.code, 'code', 'pinball')));
  });
}
