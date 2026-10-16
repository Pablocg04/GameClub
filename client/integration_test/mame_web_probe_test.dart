import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/integrated_player.dart';
import 'package:integration_test/integration_test.dart';
import 'package:webview_windows/webview_windows.dart';
import 'package:image/image.dart' as png;
import 'player_test.dart' show evaluate, until;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  for (final code in ['barline', 'cfever61', 'rcasino']) {
    testWidgets('prueba MAME web: $code', (tester) async {
      await tester.pumpWidget(MaterialApp(
          home: IntegratedPlayer(
              uri: Uri.parse('http://127.0.0.1:8691/$code'), title: code)));
      await until(
          tester, () async => find.byType(Webview).evaluate().isNotEmpty);
      await until(tester,
          () async => await evaluate(tester, '!!window.__running') == true,
          timeout: const Duration(minutes: 2));
      await Future<void>.delayed(const Duration(seconds: 8));
      debugPrint((await evaluate(tester, 'window.__mameLogs')).toString());
      await evaluate(tester,
          "window.__shot=null;requestAnimationFrame(()=>window.__shot=document.getElementById('canvas').toDataURL('image/png'));true;");
      await until(tester,
          () async => (await evaluate(tester, 'window.__shot')) is String);
      final image = await evaluate(tester, 'window.__shot') as String;
      await File(
              'C:/Users/pablo/AppData/Local/Temp/opencode/gameclub-mame-web-probe/$code.png')
          .writeAsBytes(base64Decode(image.split(',').last));
      final decoded = png.decodePng(base64Decode(image.split(',').last))!;
      final colors = <int>{};
      for (final pixel in decoded) {
        colors.add(
            pixel.r.toInt() << 16 | pixel.g.toInt() << 8 | pixel.b.toInt());
      }
      debugPrint('$code colores: ${colors.length}');
      expect(colors.length, greaterThan(3));
      expect(await evaluate(tester, 'document.getElementById("canvas").width'),
          greaterThan(100));
      await tester.pumpWidget(const SizedBox.shrink());
    }, timeout: const Timeout(Duration(minutes: 4)));
  }
}
