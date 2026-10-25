# Visual Pinball · PinMAME

## Variante TV · 0.10.1

Visual Pinball se muestra y se reproduce solo en PC y móvil. La variante TV lo
oculta en sistemas, mesas, favoritos y selectores, y no incluye su motor ni
recursos. Las mesas y guardados compartidos de la Raspberry se conservan.
El filtro de pinballs MAME sigue disponible en TV.

## Android integrado · 0.10.0

**El motor VPX/PinMAME está incluido en el APK de GameClub. No hay que instalar
otra app ni importar la mesa en un reproductor externo.** Abre la ficha y pulsa
**Jugar pinball**.

- Android 13/API 33+, proceso ARM64, OpenGL ES 3.2 o Vulkan.
- Reproducción en la actividad privada `:pinball` de GameClub; un fallo del motor
  no cierra la biblioteca Flutter.
- En móvil: Moneda, Partida, Bola, Menú y dos flippers táctiles. La superficie
  reserva espacio para esos botones; se adapta al girar el dispositivo.
- Mando: Select/Y moneda, Start partida, A lanzador, LB/LT y RB/RT flippers.
  **Start + Select / Guide / Atrás** abre continuar, reiniciar y guardar/salir.
- Los créditos del mando se secuencian; las entradas se liberan al pausar,
  perder foco o desconectar el dispositivo.
- Mesas, ROMs y NVRAM permanecen en el directorio privado preparado por GameClub,
  separados por servidor/juego. Preferencias y registro VPX: directorio de
  soporte `pinball/saves/<servidor>/<juego>/10.8/`.

El APK móvil universal conserva sus demás motores para ARM32 y x86_64. VPX utiliza
solo ARM64; en los otros procesos se explica el requisito antes de descargar.
El APK TV no incluye VPX desde 0.10.1.

El tamaño del APK aumenta porque contiene las bibliotecas del motor. Su origen
y SHA-256 están fijados en `client/platform-config/pinball_runtime.json`.
Preparación para compilar: `python tools/prepare_android_pinball.py`.

## Corrección de controles Windows · 0.9.1

El host nativo de GameClub activa la ventana VPX y evita que la mesa quede en
pausa al arrancar. Presenta una ayuda de controles y un menú propio:

| Acción | Teclado | Mando |
|---|---|---|
| Añadir moneda | 5 | Select / Back o Y |
| Iniciar partida | 1 | Start |
| Lanzar la bola | Intro | A |
| Flipper izquierdo | Mayús izquierdo | LB / L1 o LT / L2; también X |
| Flipper derecho | Mayús derecho | RB / R1 o RT / R2; también B |
| Menú | Esc, F1 o P | Start + Select / Guide |

El menú permite **Continuar**, **Reiniciar mesa** y **Guardar y volver a la
biblioteca**. Se recorre con cruceta y A; B continúa. También admite teclado y
ratón. Espacio da un golpe a la mesa: no es el lanzador.

Las monedas del mando se espacian automáticamente para respetar el retardo del
script PinMAME; Start espera a que se registren los créditos pendientes. No se
envían pulsaciones al cambiar a otra aplicación y se liberan al pausar o
desconectar el mando.

En Attack from Mars se prepara una vez la inicialización de NVRAM y se recarga
la mesa; puede tardar alrededor de un minuto. Se conservan las partidas y los
originales. Los arranques siguientes mantienen el tiempo de encendido de la ROM.

La integración Android está incluida desde 0.10.0, con los controles y el menú
descritos arriba.

GameClub 0.9.0 añade **Visual Pinball · PinMAME** (`vpinball`) y un filtro
para los pinballs de vídeo de MAME. Son dos rutas de reproducción distintas.

## Añadir una mesa desde la app

1. Prepara **un ZIP o VPXZ por mesa** con un único `.vpx`.
2. Incluye las ROMs ZIP que pide el script y sus dependencias padre, sin
   descomprimir los chips. Conserva sus nombres originales.
3. Añade, si existen, el panel `.directb2s`, música y script `.vbs` standalone.
   Un script externo debe tener el mismo nombre base que la mesa y estar a su lado.
4. En GameClub, pulsa **Añadir juegos**, selecciona el paquete, elige
   **Visual Pinball · PinMAME** y pulsa **Subir**.
5. Abre su ficha y pulsa **Jugar pinball**, en Windows o Android compatible.

Ejemplo de contenido:

```text
Attack from Mars (Bally 1995) g5k 1.3.11.vpx
Attack from Mars (Bally 1995) full dmd.directb2s
afm_113b.zip
afm_113.zip
```

Esta mesa pide `afm_113b`; `afm_113` aporta los chips de sonido de su padre.
GameClub prepara las ROMs bajo `pinmame/roms/`, ajusta el nombre del panel al de
la mesa y normaliza la carpeta `music/`, conservando el paquete original.

No subas cada ZIP de ROM como un juego. El servidor comprueba la estructura de
la mesa y la presencia de ROMs candidatas; la auditoría final de chips/CRC y la
compatibilidad del script corresponden al motor. Se admite un `.vpx` suelto
únicamente si no necesita PinMAME ni otros archivos externos.

Límites: 4 GiB por paquete, 8 GiB descomprimidos y 10 000 archivos. Se rechazan
rutas inválidas, enlaces, archivos cifrados, destinos incompatibles y ejecutables.

Para crear y validar un paquete local desde una carpeta:

```powershell
python tools/prepare_pinball_package.py "C:\mis-mesas\Una mesa" "C:\paquetes\Una mesa.zip"
```

Guarda la salida fuera de la carpeta de entrada. Esta herramienta no transfiere
archivos a la Raspberry.

## Windows

El cliente descarga del servidor el motor portátil oficial **VPX BGFX 64 bits**,
versión fijada `v10.8.1-5436-af26b2d93`, con PinMAME y scripts incluidos.
Comprueba SHA-256 del ZIP y de sus archivos antes de ejecutarlo. El servidor
descarga el ZIP oficial de GitHub si todavía no está en su caché.

No requiere registrar componentes COM. La primera descarga del motor ocupa
aproximadamente 203 MiB, además del paquete de la mesa.

- Mesas y ROMs preparadas: `Documentos/GameClub/pinball/<servidor>/<juego>/table/`.
- NVRAM y configuración PinMAME: `table/pinmame/nvram/` y `table/pinmame/cfg/`.
- Preferencias VPX y registros: `%APPDATA%/com.gameclub/gameclub/pinball/saves/<servidor>/<juego>/`.
- Motor reutilizable: `%APPDATA%/com.gameclub/gameclub/pinball/runtime/`.

Al actualizar el paquete se conservan los archivos mutables de configuración y
NVRAM. No se sincronizan las partidas entre dispositivos.

Controles habituales: **5** moneda, **1** partida, **Enter** lanzador,
**Shift izquierdo/derecho** flippers y **Esc** menú. El script o la configuración
del motor pueden cambiar esas asignaciones; el menú del motor permite ajustarlas.
Attack from Mars completa automáticamente la preparación inicial. Otras mesas
que muestren **Factory settings restored** pueden necesitar **Reiniciar mesa**
en el menú para completar su primer encendido.

La disposición del marcador y del panel depende de la mesa y de la configuración
de pantallas del motor. Las mesas con marcador propio pueden necesitar desactivar
ScoreView o recolocarlo en sus ajustes VPX.

## Android móvil

Desde 0.10.0 se reproduce dentro de GameClub con las bibliotecas oficiales
incluidas. GameClub comprueba API, ABI del proceso y gráficos antes de preparar
la mesa. Algunas mesas siguen necesitando el script standalone de su autor.
Un Android antiguo o x86_64 puede seguir jugando los pinballs MAME compatibles.

## Pinballs MAME

El icono de bola junto a la búsqueda filtra las familias `pbaction`, `pinbo`,
`speedbal`, `spbactn`, `gcpinbal`, `galspnbl`, `hotpinbl`, `timescan`, `pbchmp95`
y `vspinbal`, incluidos sus clones por nombre. Conservan la ruta arcade nativa,
sus controles y la preparación de dependencias MAME. El filtro es una lista de
familias conocidas, no una clasificación exhaustiva del catálogo MAME.

## Verificación

Se ha abierto Attack from Mars g5k 1.3.11 en Windows desde el paquete descargado
por GameClub: texturas, PinMAME, ROM hija/padre, panel B2S, audio, créditos,
salida y reapertura con NVRAM. Los originales del escritorio permanecen intactos.
En Android se ha abierto una mesa de ejemplo oficial dentro de GameClub usando
el motor ARM64 real, mediante traducción en un AVD x86_64: Vulkan, vídeo 3D,
movimiento del flipper táctil, menú Start + Select, continuación y salida a la
biblioteca. No se ha ejecutado aún en un teléfono/TV ARM64 físico; el emulador
no mide el rendimiento del Snapdragon del propietario.

Banco Android reproducible con un APK ARM64 de pruebas y una mesa local:

```powershell
python tools/check_android_pinball.py --adb "C:\Android\platform-tools\adb.exe" --device emulator-5580 --root "C:\temporal\android-pinball" --table "C:\pruebas\exampleTable.vpx"
```

Para que un AVD con traducción ARM64 ejecute el proceso ARM64 y no el x86_64:
`flutter build apk --debug --flavor mobile --target-platform android-arm64 -Pdisable-abi-filtering=true -PgameclubArm64Only=true`.
La distribución normal utiliza el APK universal.

Banco local reproducible (captura únicamente la ventana VPX de la prueba):

```powershell
python tools/run_pinball_windows_test.py --flutter "C:\flutter\bin\flutter.bat" --root "C:\temporal\pinball-test" --package "C:\paquetes\Mi mesa.zip"
```

El servidor de prueba escucha solo en `127.0.0.1:8697`. Necesita el runtime
fijado en `data/pinball-runtime/v1/windows-x86_64/vpx.zip`, que se prepara con
`python tools/fetch_pinball_runtime.py`.

La Raspberry tiene el servidor 0.9.0 y la caché del motor precargados. Comprobación
remota de API, registro, descarga SHA-256 y filtro MAME, sin subir juegos:

```powershell
python tools/check_pinball_server.py --server http://192.168.0.47:8001
```
