# Visual Pinball · PinMAME

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

Esta integración del mando y del menú es para Windows. Android sigue usando
la aplicación oficial externa de VPX y sus controles.

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
5. Abre su ficha y pulsa **Jugar pinball** en Windows o **Importar en VPX** en Android.

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

## Android móvil y TV

Requiere **Android 13 o posterior, ARM64** y la app oficial
[`org.vpinball.vpinball_bgfx`](https://github.com/vpinball/vpinball/releases).
GameClub comprueba estos requisitos antes de descargar/preparar la mesa.

El cliente exporta un `.vpxz` y lo entrega mediante un URI temporal de lectura a
Visual Pinball oficial. **Confirma la importación y abre la mesa dentro de VPX**;
los controles y ajustes de reproducción pertenecen a esa aplicación. Algunas
mesas requieren un script adaptado a standalone. La interfaz oficial y el soporte
del mando deben comprobarse en la TV ARM64 concreta.

Los APKs GameClub siguen incluyendo sus motores arcade y de consolas para las
arquitecturas anteriores. VPX no está integrado en esos APKs; un Android antiguo
o x86_64 puede seguir jugando los pinballs MAME compatibles.

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
También se comprueba el error Android por ausencia del reproductor oficial antes
de descargar, y el rechazo de archivos fuera de `pinball-share`. El AVD x86_64
anuncia ARM64 mediante traducción: no equivale a probar VPX en hardware ARM64.
No se ha ejecutado VPX en un dispositivo Android ARM64 físico.

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
