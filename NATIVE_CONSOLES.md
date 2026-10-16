# NES y Atari 2600 nativas · GameClub 0.7.0

NES utiliza **Nestopia UE** y Atari 2600 utiliza **Stella**, dentro del mismo host
C++/SDL/libretro que arcade. Se ejecutan a pantalla completa en Windows, Android
móvil y Android TV, sin WebView ni otra aplicación de emulación.

Los motores vienen incluidos en las tres apps. Se extraen a una caché local y
se comprueban por tamaño y SHA-256, tanto el paquete como el binario. El registro
es `client/assets/native_console_cores.json`. No se incluyen juegos en las apps.

## Biblioteca y formatos

| Consola | Carpeta del servidor | ROMs |
|---|---|---|
| NES | `roms/nes/` | `.nes`, `.unf`, `.unif` |
| Atari 2600 | `roms/atari2600/` | `.bin`, `.a26`, `.rom` |

Se admiten mayúsculas y ZIPs que contengan **una sola ROM** de la consola. Los
ZIPs con varios juegos deben separarse. Los estados `.sta` no se catalogan ni
se ejecutan como juegos: contienen una instantánea de una partida de otro
emulador, dependiente de su versión. Los `.sta` del pack local incluyen una
cabecera `03070300state` y datos del cartucho/CPU. No se importan como guardados
de GameClub y los originales se conservan.

El servidor incorpora las dos consolas a instalaciones nuevas y existentes al
actualizarlo. También pueden registrarse desde su API como sistemas adicionales.
Como los sistemas vacíos se ocultan en la biblioteca, aparecerán al añadir ROMs.
La colección local del escritorio solo se ha utilizado para pruebas; no se ha
subido a la Raspberry.

## Controles y guardados

- Cruceta o stick: movimiento. NES: A/B; X/Y ofrecen las funciones del núcleo.
- Atari: A o B activan Fire. Start corresponde a **RESET**; Select a **GAME SELECT**.
- NES: Start inicia y Select cambia la opción cuando lo admite el juego.
- Teclado Windows: flechas, Z=A, X=B, Enter=Start, 5=Select.
- Menú: Start+Select, Mode o Atrás; Escape en Windows. A/OK confirma; B continúa.
- Móvil: controles multitáctiles y orientación vertical, horizontal o automática.
- SRAM de cartuchos NES con batería: `battery.srm`, guardada localmente por
  biblioteca/juego/motor. Atari normalmente no tiene SRAM; el menú no convierte
  los `.sta` externos ni proporciona importación de estados de otros emuladores.

## Verificación

- 57 pruebas del servidor, 26 del cliente y dos de C++; análisis Flutter limpio.
- Windows: Super Mario Bros. y Super Mario Bros. 3, aproximadamente 60 FPS;
  Pac-Man Atari NTSC, aproximadamente 60 FPS, y PAL, aproximadamente 50 FPS.
  Comprobados vídeo, audio no silencioso sostenido, entradas, pausa, continuación
  y cierre con `tools/check_native_consoles.py`.
- Google TV API 36 emulado: NES y Atari con los motores Android x86_64 incluidos,
  vídeo, audio, botones, ejes, menú, cierre y segundo arranque.
- Variante móvil en el emulador: NES en vertical, controles táctiles, audio,
  menú, cierre y segundo arranque.
- APKs release: NES desde la biblioteca móvil, persistencia de orientación y
  salida; Atari desde la biblioteca TV, salida y navegación por mando recuperada.
- Durante la preparación inicial se registraron los dos sistemas vacíos mediante
  su API, sin publicar las ROMs de prueba del escritorio.
- Estas medidas de Windows y emulación Android no son medidas de la TV física.

`tools/fetch_native_cores.py --consoles-only` prepara paquetes y huellas conservando
las versiones arcade. No se ejecuta como parte de una compilación normal.
