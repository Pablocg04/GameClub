import 'package:flutter/material.dart';

/// Shared visual language for the library, dialogs and controller focus.
abstract final class Retro {
  static const ink = Color(0xff100b20);
  static const background = Color(0xff21123d);
  static const panel = Color(0xff352052);
  static const purple = Color(0xff8549ed);
  static const lilac = Color(0xffc5a1ff);
  static const cream = Color(0xfffff4dc);
  static const yellow = Color(0xffffd45b);
  static const pink = Color(0xffff79b8);
  static const mint = Color(0xff75e5ca);
  static const muted = Color(0xffc2b5d8);

  static TextStyle pixel(double size, {Color color = cream}) => TextStyle(
      fontFamily: 'PressStart2P', fontSize: size, height: 1.6, color: color);

  static Color systemColor(String id) => switch (id) {
        'nes' || 'psx' || 'ps2' => pink,
        'gba' || 'gb' || 'gbc' || 'nds' => mint,
        'mame' || 'atari2600' => yellow,
        'vpinball' || 'snes' || 'n64' => lilac,
        _ => const Color(0xff8bc8ff),
      };

  static ThemeData theme() {
    const shape = PixelBorder();
    final base = ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: background,
        colorScheme: const ColorScheme.dark(
            primary: lilac,
            onPrimary: ink,
            secondary: mint,
            onSecondary: ink,
            surface: panel,
            onSurface: cream,
            error: pink,
            onError: ink));
    return base.copyWith(
      textTheme: base.textTheme.apply(bodyColor: cream, displayColor: cream),
      appBarTheme: const AppBarTheme(
          backgroundColor: ink,
          foregroundColor: cream,
          surfaceTintColor: Colors.transparent,
          elevation: 0),
      dividerTheme: const DividerThemeData(color: Color(0xff624480)),
      dialogTheme: DialogThemeData(
          backgroundColor: panel,
          shape: shape,
          titleTextStyle: pixel(12),
          insetPadding: const EdgeInsets.all(16)),
      cardTheme: const CardThemeData(color: panel, shape: shape, elevation: 0),
      filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
              backgroundColor: yellow,
              foregroundColor: ink,
              shape: shape,
              textStyle: const TextStyle(fontWeight: FontWeight.w800),
              padding:
                  const EdgeInsets.symmetric(horizontal: 20, vertical: 16))),
      textButtonTheme: TextButtonThemeData(
          style: TextButton.styleFrom(
              foregroundColor: cream,
              shape: shape,
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 14))),
      outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
              foregroundColor: cream,
              shape: shape,
              side: const BorderSide(color: lilac, width: 2))),
      chipTheme: base.chipTheme.copyWith(
          shape: shape,
          side: const BorderSide(color: ink, width: 2),
          backgroundColor: panel,
          selectedColor: purple,
          checkmarkColor: yellow,
          labelStyle: const TextStyle(color: cream),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10)),
      inputDecorationTheme: const InputDecorationTheme(
          filled: true,
          fillColor: ink,
          hintStyle: TextStyle(color: muted),
          border: OutlineInputBorder(borderRadius: BorderRadius.zero),
          enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.zero,
              borderSide: BorderSide(color: Color(0xff624480), width: 2)),
          focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.zero,
              borderSide: BorderSide(color: mint, width: 3))),
      snackBarTheme: const SnackBarThemeData(
          backgroundColor: cream,
          contentTextStyle: TextStyle(color: ink),
          actionTextColor: background),
      progressIndicatorTheme: const ProgressIndicatorThemeData(color: mint),
    );
  }
}

/// Stepped corners on the same pixel grid as the illustrations.
class PixelBorder extends OutlinedBorder {
  const PixelBorder(
      {super.side = const BorderSide(color: Retro.ink, width: 3)});

  Path outline(Rect r) {
    final step = (r.shortestSide / 5).clamp(0.0, 6.0);
    return Path()
      ..moveTo(r.left + step * 2, r.top)
      ..lineTo(r.right - step * 2, r.top)
      ..lineTo(r.right - step * 2, r.top + step)
      ..lineTo(r.right - step, r.top + step)
      ..lineTo(r.right - step, r.top + step * 2)
      ..lineTo(r.right, r.top + step * 2)
      ..lineTo(r.right, r.bottom - step * 2)
      ..lineTo(r.right - step, r.bottom - step * 2)
      ..lineTo(r.right - step, r.bottom - step)
      ..lineTo(r.right - step * 2, r.bottom - step)
      ..lineTo(r.right - step * 2, r.bottom)
      ..lineTo(r.left + step * 2, r.bottom)
      ..lineTo(r.left + step * 2, r.bottom - step)
      ..lineTo(r.left + step, r.bottom - step)
      ..lineTo(r.left + step, r.bottom - step * 2)
      ..lineTo(r.left, r.bottom - step * 2)
      ..lineTo(r.left, r.top + step * 2)
      ..lineTo(r.left + step, r.top + step * 2)
      ..lineTo(r.left + step, r.top + step)
      ..lineTo(r.left + step * 2, r.top + step)
      ..close();
  }

  @override
  EdgeInsetsGeometry get dimensions => EdgeInsets.all(side.width);
  @override
  PixelBorder copyWith({BorderSide? side}) =>
      PixelBorder(side: side ?? this.side);
  @override
  ShapeBorder scale(double t) => PixelBorder(side: side.scale(t));
  @override
  Path getOuterPath(Rect rect, {TextDirection? textDirection}) => outline(rect);
  @override
  Path getInnerPath(Rect rect, {TextDirection? textDirection}) =>
      outline(rect.deflate(side.width));
  @override
  void paint(Canvas canvas, Rect rect, {TextDirection? textDirection}) {
    if (side.style == BorderStyle.none || side.width == 0) return;
    canvas.drawPath(
        Path.combine(PathOperation.difference, outline(rect),
            outline(rect.deflate(side.width))),
        Paint()..color = side.color);
  }
}

class PixelPanel extends StatelessWidget {
  const PixelPanel(
      {super.key,
      required this.child,
      this.color = Retro.panel,
      this.padding = EdgeInsets.zero});
  final Widget child;
  final Color color;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) => DecoratedBox(
      decoration: const ShapeDecoration(
          shape: PixelBorder(),
          shadows: [BoxShadow(color: Retro.ink, offset: Offset(4, 5))]),
      child: Material(
          color: color,
          shape: const PixelBorder(),
          clipBehavior: Clip.hardEdge,
          child: Padding(padding: padding, child: child)));
}

class PixelBackdrop extends StatelessWidget {
  const PixelBackdrop({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) =>
      CustomPaint(painter: const _BackdropPainter(), child: child);
}

class _BackdropPainter extends CustomPainter {
  const _BackdropPainter();
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawColor(Retro.background, BlendMode.srcOver);
    final paint = Paint()..color = const Color(0xff392253);
    for (double x = 12; x < size.width; x += 28) {
      for (double y = 12; y < size.height; y += 28) {
        canvas.drawRect(Rect.fromLTWH(x, y, 2, 2), paint);
      }
    }
  }

  @override
  bool shouldRepaint(_BackdropPainter oldDelegate) => false;
}

/// Original code-drawn pixel art; no network images or bitmap scaling.
class PixelController extends StatelessWidget {
  const PixelController({super.key, this.color = Retro.lilac, this.size = 120});
  final Color color;
  final double size;
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
      child: SizedBox(
          width: size,
          height: size * .65,
          child: CustomPaint(painter: _ControllerPainter(color))));
}

class _ControllerPainter extends CustomPainter {
  const _ControllerPainter(this.color);
  final Color color;
  static const pixels = [
    '00000000000000000000',
    '00001111111111110000',
    '00112222222222221100',
    '01122222222222222110',
    '01222322222222422210',
    '01223332222224242210',
    '01222322222222422210',
    '01222222111222222210',
    '01222222222222222210',
    '01122221111112222110',
    '00111110000001111100',
    '00000000000000000000',
  ];
  @override
  void paint(Canvas canvas, Size size) {
    final unit = (size.width / 20).floorToDouble();
    final dx = ((size.width - unit * 20) / 2).floorToDouble();
    final dy = ((size.height - unit * 12) / 2).floorToDouble();
    final colors = [
      Colors.transparent,
      Retro.ink,
      color,
      Retro.ink,
      Retro.pink
    ];
    for (var y = 0; y < pixels.length; y++) {
      for (var x = 0; x < pixels[y].length; x++) {
        final value = int.parse(pixels[y][x]);
        if (value == 0) continue;
        canvas.drawRect(
            Rect.fromLTWH(dx + x * unit, dy + y * unit, unit, unit),
            Paint()
              ..color = colors[value]
              ..isAntiAlias = false);
      }
    }
  }

  @override
  bool shouldRepaint(_ControllerPainter oldDelegate) =>
      color != oldDelegate.color;
}
