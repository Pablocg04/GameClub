/// Los juegos de sesión corta arrancan de cero; el resto conserva sus partidas.
bool persistsGameProgress(String system) =>
    !const {'mame', 'nes', 'atari2600', 'vpinball'}.contains(system);
