import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/api.dart';
import 'package:gameclub/pinball_player.dart';
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('VPX portátil: prepara paquete y abre el motor verificado',
      (tester) async {
    final api = GameClubApi(
        const String.fromEnvironment('PINBALL_TEST_SERVER',
            defaultValue: 'http://127.0.0.1:8697'),
        '');
    final game =
        (await api.list('/api/games', {'system_id': 'vpinball'})).first;
    await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: Text('Prueba de pinball'))));
    final player = PinballPlayer(api,
        onStarted: (pid) => debugPrint('PINBALL_ENGINE_PID $pid'));
    await player.play(game).timeout(const Duration(minutes: 5));
    debugPrint('PINBALL_CLOSED');
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  }, timeout: const Timeout(Duration(minutes: 8)));
}
