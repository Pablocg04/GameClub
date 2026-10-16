import 'dart:async';
import 'dart:convert';
import 'package:flutter/services.dart';
import 'television.dart';

class AndroidGamepad {
  AndroidGamepad({required this.execute, required this.onMenu});
  final Future<void> Function(String) execute;
  final void Function() onMenu;
  static const events = EventChannel('gameclub/gamepad');
  StreamSubscription<dynamic>? subscription;
  Timer? timer;
  final pending = <Map<String, dynamic>>[];
  final axes = <int, Map<String, dynamic>>{};
  bool disposed = false;
  Future<void>? stopping;
  static int nextOwner = 0;
  final String owner =
      'pad-${DateTime.now().microsecondsSinceEpoch}-${nextOwner++}';

  Future<void> start() async {
    if (disposed) return;
    subscription =
        events.receiveBroadcastStream({'owner': owner}).listen((dynamic raw) {
      if (disposed) return;
      final event = Map<String, dynamic>.from(raw as Map);
      if (event['type'] == 'menu') {
        timer?.cancel();
        timer = null;
        pending.clear();
        axes.clear();
        onMenu();
        return;
      }
      if (event['type'] == 'reset') {
        pending.clear();
        axes.clear();
      }
      if (event['type'] == 'disconnect') {
        axes.remove(event['device']);
        pending.removeWhere((value) => value['device'] == event['device']);
      }
      if (event['type'] == 'axes') {
        axes[event['device'] as int] = event;
      } else {
        pending.add(event);
      }
      timer ??= Timer(const Duration(milliseconds: 8), flush);
    }, onError: (_) {});
    await active(true);
  }

  Future<void> active(bool value, {bool restoreDisplay = false}) async {
    if (disposed && value) return;
    await DevicePlatform.channel.invokeMethod<void>('playerActive', {
      'active': value,
      'fast': DevicePlatform.fastTelevision,
      'restoreDisplay': restoreDisplay,
      'owner': owner
    });
  }

  Future<void> flush() async {
    timer = null;
    if (disposed) return;
    final batch = [...pending, ...axes.values];
    pending.clear();
    axes.clear();
    try {
      await execute(
          'window.gameclubControllerInput?.(${jsonEncode(batch)});true;');
    } catch (_) {/* Puede estar cambiando de núcleo. */}
  }

  Future<void> dispose() => stopping ??= stop();
  Future<void> stop() async {
    disposed = true;
    timer?.cancel();
    pending.clear();
    axes.clear();
    try {
      await active(false, restoreDisplay: true);
    } on PlatformException {/* Actividad ya cerrada. */} finally {
      await subscription?.cancel();
    }
  }
}
