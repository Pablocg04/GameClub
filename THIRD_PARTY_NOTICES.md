# Componentes de terceros

## Visual Pinball y PinMAME · 0.9.0

El motor Windows se descarga sin modificaciones desde la distribución oficial
de [Visual Pinball](https://github.com/vpinball/vpinball), tag
`v10.8.1-5436-af26b2d93` (BGFX Windows MinGW x64). URL, tamaño, SHA-256 y huellas
por archivo: `server/app/pinball_runtime.json`. Los avisos originales se conservan
en la distribución descargada, incluidos `docs/license.txt` y los de sus plugins.
La mayoría de fuentes Visual Pinball usan GPL-3.0-or-later; los archivos aún no
relicenciados conservan su licencia histórica derivada de MAME, según el aviso
original `docs/license.txt`. Sus componentes y scripts mantienen sus licencias
respectivas. Fuentes de PinMAME:
<https://github.com/vpinball/pinmame>.

En Android se abre la aplicación oficial externa de VPX; GameClub no redistribuye
su APK. Las mesas, paneles, sonidos y ROMs del usuario no forman parte de GameClub.
Guía y requisitos: [PINBALL.md](PINBALL.md).

## Reproductor nativo de arcade y consolas · 0.7.0

- **SDL 3.4.18**, licencia zlib, sin modificaciones:
  <https://github.com/libsdl-org/SDL/tree/release-3.4.18>.
  Los archivos originales y sus SHA-256 están fijados en
  `tools/prepare_native_engine.py`. Aviso completo en
  `client/assets/native-notices.txt` (incluido en el APK y el paquete Windows).
- Cabecera de la API libretro de RetroArch 1.22.2, licencia MIT:
  <https://github.com/libretro/RetroArch/blob/v1.22.2/libretro-common/include/libretro.h>.
- Binarios nativos oficiales de <https://buildbot.libretro.com/>, sin modificaciones.
  Registro exacto de archivos y SHA-256: `server/app/native_cores.json`.
  Fuentes y licencias de los motores:
  - <https://github.com/libretro/mame2003-plus-libretro> (licencia MAME histórica).
  - <https://github.com/libretro/mame2003-libretro> (licencia MAME histórica).
  - <https://github.com/libretro/FBNeo> (licencia de FinalBurn Neo).
  - <https://github.com/libretro/mame> (MAME, GPL-2.0-or-later y componentes BSD).
  - <https://github.com/libretro/nestopia> (Nestopia UE, GPL-2.0).
  - <https://github.com/libretro/stella> (Stella, GPL-2.0).

NES y Atari 2600 incluyen los paquetes originales del motor en los recursos de las
apps. `client/assets/native_console_cores.json` fija sus huellas para Windows,
Android ARM32, ARM64 y x86_64. No se incluyen juegos ni estados de la biblioteca.

Los metadatos históricos se extraen mediante `-listxml` del MAMEUI 0.130u3 del
pack del usuario. No se incluye su ejecutable ni ninguna ROM en el código.

## Imágenes del catálogo

Libretro Thumbnails: <https://github.com/libretro-thumbnails/libretro-thumbnails>.
LaunchBox Games Database: <https://gamesdb.launchbox-app.com/>.
GameTDB: <https://www.gametdb.com/>.
Las carátulas y capturas conservan los derechos de sus autores, editoras y los
créditos de las fuentes indicadas por el catálogo.

## Reproductor integrado

- **EmulatorJS 4.2.3**, distribuido por el proyecto EmulatorJS, licencia GPL-3.0.
  Fuente de la versión utilizada: <https://github.com/EmulatorJS/EmulatorJS/tree/v4.2.3>.
  Licencia: <https://github.com/EmulatorJS/EmulatorJS/blob/v4.2.3/LICENSE>.
- Los núcleos de emulación conservan sus licencias y atribuciones propias.
  Sus paquetes incluyen `license.txt` y metadatos de repositorio, mostrados por el
  apartado de información del reproductor:
  - Gambatte: <https://github.com/libretro/gambatte-libretro>.
  - mGBA: <https://github.com/libretro/mgba>.
  - DeSmuME: <https://github.com/libretro/desmume>.
  - Snes9x: <https://github.com/libretro/snes9x>.
  - Mupen64Plus-Next: <https://github.com/libretro/mupen64plus-libretro-nx>.
  - MAME 2003-Plus: <https://github.com/libretro/mame2003-plus-libretro>.
    Mantiene su licencia MAME histórica, incluida en el paquete del núcleo.
  - MAME 2003: <https://github.com/libretro/mame2003-libretro>.
  - FinalBurn Neo: <https://github.com/libretro/FBNeo>.
    Sus licencias y metadatos se incluyen en los paquetes correspondientes.

Los recursos de EmulatorJS se obtienen del CDN oficial, fijados a la versión
4.2.3 y cacheados localmente. El adaptador de GameClub se encuentra en
`client/lib/player_host.dart`; los binarios de los núcleos no se modifican.

## MAME web por controlador

MAME 0.232: <https://github.com/mamedev/mame/tree/mame0232>, con licencia general
GPL-2.0-or-later y componentes con sus licencias BSD correspondientes.
Distribuciones WebAssembly utilizadas por Emularity:
<https://archive.org/details/emularity_engine_v1>.
Fuente del cargador de referencia: <https://github.com/db48x/emularity>.
GameClub utiliza su propio adaptador `client/lib/mame_web_player.dart` y comprueba
las huellas de los motores en `server/app/mame_web.py`; no modifica esos binarios.

## Vistas web

- `webview_windows` 0.4.0: <https://github.com/jnschulze/flutter-webview-windows>, MIT.
- `webview_flutter`: <https://github.com/flutter/packages/tree/main/packages/webview_flutter>, BSD-3-Clause.

Las licencias del resto de dependencias Flutter se recopilan durante la
compilación en su registro de licencias. Los programas de `tools/fixtures/` son
programas de prueba del proyecto, no juegos de la biblioteca.
