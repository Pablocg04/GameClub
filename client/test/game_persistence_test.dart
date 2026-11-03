import 'package:flutter_test/flutter_test.dart';
import 'package:gameclub/game_persistence.dart';

void main() {
  test('solo MAME, Atari 2600, NES y VPX arrancan sin partida persistente', () {
    for (final system in ['mame', 'atari2600', 'nes', 'vpinball']) {
      expect(persistsGameProgress(system), false, reason: system);
    }
    for (final system in ['nds', 'gb', 'gbc', 'gba', 'snes', 'n64', 'psx']) {
      expect(persistsGameProgress(system), true, reason: system);
    }
  });
}
