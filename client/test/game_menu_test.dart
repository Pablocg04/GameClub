import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/game_menu.dart';

void main() {
  for (final save in [false, true]) {
    testWidgets(
        save
            ? 'Nintendo DS mantiene la salida con guardado'
            : 'el menú sin persistencia muestra Salir', (tester) async {
      await tester.pumpWidget(
          MaterialApp(home: Scaffold(body: GameMenu(saveProgress: save))));
      expect(find.text('Salir'), save ? findsNothing : findsOneWidget);
      expect(find.text('Guardar y volver a la biblioteca'),
          save ? findsOneWidget : findsNothing);
    });
  }
  testWidgets('el menú se recorre con cruceta y A confirma salir',
      (tester) async {
    String? action;
    await tester.pumpWidget(MaterialApp(
        home: Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () async {
                      action = await showDialog<String>(
                          context: context, builder: (_) => const GameMenu());
                    },
                    child: const Text('Abrir'))))));
    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú juego 0');
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
    await tester.pumpAndSettle();
    expect(FocusManager.instance.primaryFocus?.debugLabel, 'Menú juego 1');
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonA);
    await tester.pumpAndSettle();
    expect(action, 'exit');
    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.gameButtonB);
    await tester.pumpAndSettle();
    expect(action, 'resume');
  });
}
