import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// El menú conserva un foco Flutter explícito, independiente de la vista del motor.
class GameMenu extends StatefulWidget {
  const GameMenu({super.key, this.configureControls = false});
  final bool configureControls;
  @override
  State<GameMenu> createState() => _GameMenuState();
}

class _GameMenuState extends State<GameMenu> {
  late final actions = [
    'resume',
    if (widget.configureControls) 'controls',
    'exit'
  ];
  late final nodes = List.generate(
      actions.length, (i) => FocusNode(debugLabel: 'Menú juego $i'));
  @override
  void dispose() {
    for (final node in nodes) {
      node.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Focus(
      onKeyEvent: (_, event) {
        if (event is! KeyDownEvent) return KeyEventResult.ignored;
        final key = event.logicalKey;
        final current = nodes
            .indexWhere((node) => node.hasFocus)
            .clamp(0, nodes.length - 1);
        if ({
          LogicalKeyboardKey.arrowLeft,
          LogicalKeyboardKey.arrowUp,
          LogicalKeyboardKey.arrowRight,
          LogicalKeyboardKey.arrowDown
        }.contains(key)) {
          final delta = {
            LogicalKeyboardKey.arrowLeft,
            LogicalKeyboardKey.arrowUp
          }.contains(key)
              ? -1
              : 1;
          nodes[(current + delta + nodes.length) % nodes.length].requestFocus();
          return KeyEventResult.handled;
        }
        if ({
          LogicalKeyboardKey.gameButtonA,
          LogicalKeyboardKey.enter,
          LogicalKeyboardKey.select
        }.contains(key)) {
          Navigator.pop(context, actions[current]);
          return KeyEventResult.handled;
        }
        if ({LogicalKeyboardKey.gameButtonB, LogicalKeyboardKey.escape}
            .contains(key)) {
          Navigator.pop(context, 'resume');
          return KeyEventResult.handled;
        }
        return KeyEventResult.ignored;
      },
      child: AlertDialog(
          title: const Text('Menú del juego'),
          content: const Text(
              'Cruceta para elegir, A/OK para aceptar y B/Atrás para continuar.'),
          actions: List.generate(
              actions.length,
              (i) => TextButton(
                  focusNode: nodes[i],
                  autofocus: i == 0,
                  onPressed: () => Navigator.pop(context, actions[i]),
                  child: Text(switch (actions[i]) {
                    'resume' => 'Continuar',
                    'controls' => 'Configurar controles MAME',
                    _ => 'Guardar y volver a la biblioteca'
                  })))));
}
