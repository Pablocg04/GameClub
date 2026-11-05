# Componentes de terceros

## Cliente Nintendo Switch · 0.12.0

Cliente propio C++/SDL2, compilado con devkitA64 r30 y libnx 4.12.0. Los paquetes
oficiales de devkitPro están fijados con versión/tamaño/SHA-256 en
`switch-client/toolchain-lock.json`. El compilador no se redistribuye.

- [libnx](https://github.com/switchbrew/libnx), licencia ISC.
- [SDL2 2.28.5](https://github.com/libsdl-org/SDL/tree/release-2.28.5) y
  [SDL2_image 2.0.4](https://github.com/libsdl-org/SDL_image/tree/release-2.0.4),
  licencia zlib.
- [curl 7.69.1](https://github.com/curl/curl/tree/curl-7_69_1), licencia curl/MIT.
- [Mesa 20.1.0 para Switch](https://github.com/devkitPro/mesa),
  [libdrm_nouveau](https://github.com/devkitPro/libdrm_nouveau), libpng, zlib,
  libjpeg-turbo y libwebp: avisos originales en `switch-client/licenses/`.
- [nlohmann/json 3.12.0](https://github.com/nlohmann/json/tree/v3.12.0), licencia
  MIT; cabecera y aviso íntegros en `switch-client/vendor/`.
- [Lato](https://github.com/google/fonts/tree/main/ofl/lato) y Press Start 2P,
  licencia SIL OFL 1.1. Se generan atlas de glifos para su uso en la interfaz;
  se conservan las fuentes originales y sus licencias.
- GCC/libstdc++ usan la excepción de biblioteca de ejecución; se conservan los
  avisos de esa excepción y de newlib.

Los avisos y licencias se incrustan en el RomFS del NRO. RetroArch y sus núcleos
no se incluyen ni se modifican: GameClub abre los NRO que el usuario tenga en su
SD. Fuentes y documentación de ese proyecto:
<https://github.com/libretro/RetroArch>, <https://docs.libretro.com/guides/install-libnx/>.

La vista de escritorio usada en pruebas utiliza los SDK oficiales SDL2 2.32.10
y SDL2_image 2.8.12 para Windows; esas DLL de prueba no forman parte del NRO.

## Tipografía de la biblioteca · 0.11.0

Press Start 2P, copyright 2012 The Press Start 2P Project Authors, distribuida
sin modificaciones bajo SIL Open Font License 1.1. Fuente original:
<https://github.com/google/fonts/tree/main/ofl/pressstart2p>.
La fuente y su licencia completa se incluyen en `client/assets/fonts/` y en
los tres paquetes. Los dibujos de mandos se generan con código de GameClub.

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

Desde **0.10.0**, Android móvil incluye las bibliotecas nativas y recursos del APK
oficial BGFX mobile de ese mismo tag, sin modificarlos. No instala ni abre la
aplicación VPX externa. Registro de APK, componentes y SHA-256:
`client/platform-config/pinball_runtime.json`; preparación reproducible:
`tools/prepare_android_pinball.py`. La licencia original se incluye en
`assets/pinball/licenses/VisualPinball.txt` del APK; fuentes exactas:
<https://github.com/vpinball/vpinball/tree/af26b2d9392b4c9ec3e3edff4bbd69562085a44c>.
Se reutiliza SDL 3.4.18 del proyecto y un adaptador propio de la API C de VPX,
sin modificar las bibliotecas oficiales. Se conservan las licencias de SDL_image,
SDL_ttf, FreeImage, FFmpeg, Wine VBScript y los componentes/plugins originales.
Las mesas, paneles, sonidos y ROMs del usuario no forman parte de GameClub.
Desde 0.10.1 la variante TV excluye estas bibliotecas y recursos de VPX.
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
