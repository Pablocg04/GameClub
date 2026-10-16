import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'api.dart';
import 'arcade_loader.dart';
import 'native_runtime.dart';

/// Selección y preparación de ROMsets arcade para el host SDL/libretro.
class NativeArcade extends NativeRuntime {
  NativeArcade(super.api, {super.onProgress});

  Future<void> play(Json game,
      {bool? touchControls, bool diagnostics = false}) async {
    final target = await platform();
    final support = await supportDirectory();
    final documents = await getApplicationDocumentsDirectory();
    final loader = ArcadeLoader(
        api,
        Directory(
            p.join(documents.path, 'GameClub', 'arcade-native', libraryKey)),
        onProgress: onProgress);
    final result = await loader.candidates(game, native: true);
    final plans = (result['candidates'] as List)
        .map((value) => Json.from(value as Map))
        .toList();
    final errors = <String>[];
    for (final plan in plans) {
      final name = plan['core'] as String;
      try {
        onProgress?.call('Preparando ${plan['core_name']} nativo…', null);
        final files = await loader.prepare(game, plan: plan);
        final engine = await core(target, name, support);
        final primary = files['${plan['game_code']}.zip']!;
        final saves = Directory(p.join(
            support.path, 'saves', libraryKey, game['id'] as String, name));
        await launch(engine, primary, saves,
            mode: {'barline', 'cfever61', 'rcasino'}.contains(plan['game_code'])
                ? 'cards'
                : 'arcade',
            touchControls: touchControls,
            diagnostics: diagnostics);
        await loader.remember(game, plan, native: true);
        return;
      } catch (error) {
        debugPrint('MAME nativo $name: $error');
        errors.add('${plan['core_name']}: ${GameClubApi.error(error)}');
        await loader.forget(game, native: true);
      }
    }
    final rejected = (result['rejected'] as List)
        .map((item) => '${item['core_name']}: ${item['reason']}');
    throw Exception([
      'Ningún motor nativo pudo ejecutar este ROMset.',
      ...errors,
      ...rejected
    ].join('\n'));
  }
}
