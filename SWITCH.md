# GameClub para Nintendo Switch · 0.13.0

Cliente **homebrew nativo ARM64**, independiente de Flutter, distribuido como
`GameClub-Switch.nro`. Se conecta al mismo servidor de la Raspberry que PC,
móvil y TV. Incluye biblioteca retro morada, carátulas, filtros por consola,
búsqueda, favoritos y ajustes de servidor/token desde el teclado de Switch.
La versión 0.13.0 añade integración con un motor nativo experimental de Visual
Pinball/PinMAME. Se instala con el ZIP completo descrito en [SWITCH_PINBALL.md](SWITCH_PINBALL.md).

**Estado experimental:** NRO compilado y comprobado por formato y pruebas de
escritorio; todavía no ejecutado en una Switch física.

## Copiar y abrir

1. La consola debe disponer de un entorno que ejecute aplicaciones homebrew NRO.
2. Copia `GameClub-Switch.nro` a
   `sd:/switch/gameclub/GameClub-Switch.nro`.
3. Abre **GameClub** desde Homebrew Menu, con la consola conectada a la misma
   red que la Raspberry. La dirección inicial es `http://192.168.0.47:8001`.
4. Si hace falta, entra en **Ajustes**, cambia servidor/token y pulsa
   **Guardar y conectar**.
5. Para jugar, instala por separado la distribución de **RetroArch para Switch**
   y sus núcleos. La carpeta predeterminada es `sdmc:/retroarch/cores` y se puede
   cambiar en Ajustes. Se necesita un entorno Homebrew Menu que permita abrir
   otro NRO; RetroArch recomienda ejecutarlo con acceso completo a memoria.
6. Para las mesas **Visual Pinball**, instala `GameClub-Switch-Pinball-0.13.0.zip`
   en la raíz de la SD. Incluye GameClub, el motor nativo y sus recursos; estas
   mesas se abren con VPX/PinMAME y no utilizan RetroArch.

El NRO incluye sus fuentes, icono y recursos; no necesita copiar una carpeta de
assets. No incluye ROMs, BIOS ni núcleos de emulación. Guía del proyecto RetroArch:
<https://docs.libretro.com/guides/install-libnx/>.

## Controles

- Cruceta/stick izquierdo: desplazarse por juegos, menús y ajustes.
- **A:** abrir ficha, confirmar o jugar con RetroArch desde la ficha.
- **B:** cerrar ficha/mensaje o enfocar el menú lateral.
- **X:** marcar o quitar favorito en el servidor compartido.
- **Y:** buscar con el teclado de Switch.
- **L/R:** Biblioteca, Favoritos, Consolas y Ajustes.
- **ZL/ZR:** página anterior/siguiente de juegos.
- **−:** recargar la biblioteca. **+:** salir de GameClub.
- Pantalla táctil: seleccionar botones/fichas y abrir búsqueda/ajustes.

Los controles y el menú durante el juego pertenecen a RetroArch. Al salir de
RetroArch se vuelve al entorno de homebrew; abre GameClub para regresar a la
biblioteca. Esta primera versión no encadena automáticamente la vuelta.

## Sistemas y motores externos

Se muestran NES, Atari 2600, GB/GBC, GBA, SNES, MAME, Nintendo DS, N64, PSX, PSP y Visual Pinball.
La presencia en el catálogo no certifica rendimiento ni compatibilidad de todos
sus juegos. El núcleo debe existir como NRO válido antes de descargar el juego.

| Sistema | Núcleos que se buscan, en orden |
|---|---|
| NES | `nestopia`, `fceumm`, `quicknes` |
| Atari 2600 | `stella2014`, `stella` |
| GB/GBC | `gambatte`, `mgba` |
| GBA | `mgba`, `gpsp` |
| SNES | `snes9x`, `snes9x2010` |
| MAME | `mame2003_plus`, `mame2003`, `fbneo`, según el plan compatible del servidor |
| Nintendo DS | `melonds`, `desmume` |
| Nintendo 64 | `mupen64plus_next` |
| PlayStation | `pcsx_rearmed` |
| PSP | `ppsspp` |
| Visual Pinball/PinMAME | Motor independiente `switch/gameclub/pinball/GameClubPinball.nro` con sus recursos |

Se aceptan los nombres `<núcleo>_libretro_libnx.nro` y
`<núcleo>_libretro.nro`. MAME utiliza los planes del servidor, descarga ZIP
principal/padres/BIOS/CHD disponibles y conserva sus nombres dentro de una carpeta
por juego y firma de dependencias. El núcleo realiza la validación final.

Los formatos de varias partes como CUE/M3U y los archivos 7z/DSi todavía no se
preparan en este cliente. Se rechazan con un mensaje. Visual Pinball prepara sus
paquetes ZIP/VPXZ y mesas VPX para el motor nativo. Los demás sistemas sin
adaptador no aparecen en la biblioteca Switch. PC y móvil conservan Visual
Pinball; la variante TV sigue excluyendo su motor.

## Caché y guardados

Datos privados de GameClub en `sdmc:/switch/gameclub/`:

- `config.json`: servidor, token opcional y carpeta de núcleos. No lo compartas
  si contiene tu token. No se modifica el `retroarch.cfg` del usuario.
- `libraries/<servidor>/catalog.json` y `covers/`: biblioteca en caché y carátulas.
- `roms/<sistema>/<juego>/`: copias descargadas. Una revisión nueva del juego
  invalida su caché, aunque conserve el mismo tamaño.
- `saves/<sistema>/<juego>/battery/`: batería de las consolas con persistencia.
- `sessions/run-.../`: configuración temporal de cada lanzamiento. Solo se
  eliminan al arrancar de nuevo las carpetas marcadas por GameClub.
- `libraries/<servidor>/pinball-state/<mesa>/`: NVRAM/configuración del pinball y
  su registro `switch-player.log`. La caché de mesa y ROMs se guarda aparte.

MAME, NES y Atari comienzan cada apertura en una carpeta nueva, sin cargar estados
anteriores ni batería de otras sesiones. RetroArch puede escribir archivos
temporales en esa carpeta; GameClub no los reutiliza. Nintendo DS y las demás
consolas mantienen batería local y rutas estables de guardados. Se desactiva la
carga/guardado automático de instantáneas y las configuraciones por juego que
podrían sobrescribir esta política. Las BIOS de otras consolas se configuran en
la instalación de RetroArch. Las partidas no se sincronizan entre dispositivos.

## Compilación y comprobaciones

En el entorno Windows del proyecto, con Python 3.14 y Pillow:

```powershell
.\.venv\Scripts\python.exe tools/prepare_switch_toolchain.py
.\.venv\Scripts\python.exe tools/build_switch.py
```

Los paquetes oficiales de devkitPro quedan aislados en `dist/switch-toolchain`;
versiones, tamaños y SHA-256 están fijados en `switch-client/toolchain-lock.json`.
El compilador genera un ELF AArch64 y un NRO con NACP, icono y RomFS. El script
comprueba esas cabeceras, versión y presencia de recursos. Fuentes nativas en
`switch-client/src/`; licencias en `switch-client/licenses/`.

El CMake de `switch-client` compila una vista de escritorio del mismo código SDL2
y las pruebas de modelo/transporte. Necesita SDL2 y SDL2_image para Windows:

```powershell
cmake -S switch-client -B switch-client/build-host -A x64 -DSDL2_DIR=<SDL2/cmake> -DSDL2_image_DIR=<SDL2_image/cmake>
cmake --build switch-client/build-host --config Release
.\.venv\Scripts\python.exe tools/check_switch.py
```

Para renderizar sin abrir una ventana:

```powershell
switch-client/build-host/Release/gameclub_switch_preview.exe --headless --frames 240 --screenshot dist/switch-preview.png
```

**Comprobado:** compilación cruzada y estructura del NRO; 33 comprobaciones
nativas con API aislada y fixtures propios; seis vistas renderizadas y biblioteca
real consultada desde la vista de escritorio. Los fixtures no son juegos.
**Pendiente en hardware:** arranque en Homebrew Menu, red/teclado/Joy-Con reales,
apertura de los núcleos y persistencia efectiva de cada uno. La validación de
escritorio y de formato no sustituye esas pruebas en una Switch física.
Las pruebas nativas actuales incluyen extracción de VPX, CRC, rutas inseguras,
lanzamiento del motor y NVRAM estable, progreso y cancelación: 47 comprobaciones. La ejecución efectiva
de Visual Pinball/PinMAME en la consola está pendiente de la prueba física.
