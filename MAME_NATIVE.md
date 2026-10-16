# MAME nativo · GameClub 0.6.2

Desde el cliente 0.6.1 hay APKs separados para [móvil](ANDROID_MOBILE.md) y
[TV](ANDROID_TV.md). Móvil añade controles clásicos de mayor tamaño y orientación
vertical/horizontal, con los controles debajo de la imagen al jugar en vertical.

Arcade se ejecuta en un reproductor **C++/SDL3/libretro**, incluido en GameClub
para Windows, Android y Android TV. La biblioteca prepara los archivos y abre
directamente el juego a pantalla completa. No hay un segundo botón de inicio.

## Motores y compatibilidad

- MAME 2003-Plus, MAME 2003, FinalBurn Neo y MAME completo nativos.
- El servidor comprueba los chips y prepara ZIP principal, padres, BIOS y CHD
  disponibles. Si un motor rechaza la partida, se intenta el siguiente.
- Se han importado **8.002 máquinas** del XML del MAMEUI 0.130u3 del pack para
  resolver dependencias históricas. Esto no convierte el motor actual en MAME
  0.130u3: su validación final puede exigir otro ROMset o BIOS.
- MAMEUI es una interfaz Windows. La ruta multiplataforma utiliza los motores
  nativos y la interfaz de GameClub, con el mismo flujo en móvil y TV.
- World Class Bowling v1.66 dispone de un perfil nativo para su revisión histórica
  de audio, con MAME 2003-Plus. Se comprueban los CRC y tamaños de sus 17 chips
  contra `server/app/native_bowling.json`; un ZIP incompleto sigue rechazándose.
- La compatibilidad de todos los juegos y la velocidad de todos los equipos no
  están certificadas. Los ficheros originales de la biblioteca se conservan.

La primera apertura descarga el motor apropiado desde la Raspberry y lo verifica
por SHA-256. Después se reutiliza su caché. No se instala otra aplicación.
La versión de cada binario queda fijada en `server/app/native_cores.json`; el
servidor mantiene los ZIP originales en `data/native-cores/v1/`.

## Controles

| Acción | Control |
|---|---|
| Jugar | Cruceta/sticks, A/B/X/Y, L/R y gatillos del mando |
| Moneda / inicio arcade | Select / Start |
| Abrir el menú | Start + Select, Mode o Atrás; Escape en Windows |
| Elegir una opción | Cruceta; A/OK confirma |
| Continuar | B o Atrás/Escape desde el menú |
| Cerrar | **Guardar y salir** en el menú |

El móvil tiene cruceta con diagonales, botones circulares A/B/X/Y y L/R,
Select/Start y un acceso flotante al menú. Los botones aceptan multitáctil y
liberan las entradas al cancelar el contacto. Los juegos de cartas adicionales
reciben también su adaptación de teclado MAME: Z/X/C/V/B para los cinco Hold,
5 para moneda, 1 para inicio y 2 para apuesta.

Los juegos con trackball pueden recibir movimiento relativo desde la cruceta o
los sticks. En Bowling, Select introduce moneda y Start inicia; con la tarifa
predeterminada, una moneda aporta medio crédito, por lo que hacen falta dos.

El juego ocupa toda la pantalla, conservando sus proporciones. No hay barra de
aplicación ni contador permanente sobre la imagen. Los márgenes negros que
correspondan a la proporción original forman parte de esa presentación.

Se conservan SRAM/NVRAM, configuración e hiscores que escriba cada núcleo.
Las carpetas de guardado son locales y separadas por biblioteca, juego y motor.
Cambiar desde la ruta web anterior no importa automáticamente sus guardados.

## Implementación

- `client/native/player.cpp`: vídeo por textura SDL, audio, entrada de hasta
  cuatro mandos, teclado, controles táctiles, menú y cierre del núcleo.
- `client/lib/native_arcade.dart`: preparación, caché verificada, selección y
  lanzamiento del host incluido.
- Android: `NativeGameActivity` usa un proceso `:emulation` propio y devuelve el
  foco a la biblioteca. Cada partida comienza con el estado global del motor limpio.
  La tecla Atrás y el callback predictivo se unifican para no abrir/cerrar el menú
  dos veces. Las liberaciones de teclas de la actividad anterior no reactivan la ficha.
- Windows: `gameclub_native.exe` y `SDL3.dll` se distribuyen junto a `gameclub.exe`.
- `GET /api/player/native` publica las huellas y plataformas; los paquetes se
  sirven por `/api/player/native/{platform}/{core}`.
- `arcade/cores?native=true&identify=true` devuelve los planes nativos. Los clientes
  antiguos conservan el contrato anterior si no solicitan ese parámetro.

NES y Atari 2600 utilizan también el host nativo desde 0.7.0; consulta
[NATIVE_CONSOLES.md](NATIVE_CONSOLES.md). Las otras consolas integradas conservan
su motor EmulatorJS y su puente de mando Android.

## Preparación del desarrollo

```powershell
.\.venv\Scripts\python.exe tools/prepare_native_engine.py client/native/vendor
# Desde client, con Flutter en PATH:
.\bootstrap.ps1
```

El preparador verifica SDL **3.4.18** y descarga la cabecera libretro de RetroArch
**1.22.2**. Los binarios originales de SDL y los motores no se modifican. La
carpeta `vendor` queda fuera de Git. Android requiere el SDK/NDK/CMake de Flutter.

`tools/fetch_native_cores.py` genera el registro de una nueva captura de motores;
no debe ejecutarse como parte de una compilación normal. Conserva la caché que
corresponde a las huellas publicadas. `tools/deploy_native_server.py` despliega
el servidor y esa caché únicamente en el servicio GameClub de la Raspberry.

## Verificación realizada

- 56 pruebas del servidor y dos pruebas C++ de controles/diseño táctil superadas.
- Windows, Bowling v1.66 con MAME 2003-Plus: aproximadamente 60 fotogramas/s,
  entradas direccionales consumidas por el motor, muestras de audio no silenciosas,
  captura de la tirada y del marcador, y cierre correcto mediante el menú.
- En verificaciones anteriores: 20 pruebas del cliente, además del banco de integración.
- Google TV API 36 emulado: Arkanoid (MAME 2003-Plus), Metal Slug con BIOS (FBNeo),
  Barline, Casino Fever 6.1 y Royal Casino (MAME completo), con vídeo real.
- Entrada nativa por ADB, entrada táctil en los tres juegos de cartas, pausa,
  navegación por el menú, continuación, salida y una segunda apertura.
- Arkanoid alcanzó aproximadamente 60 fotogramas/s en el AVD tras el arranque.
  Esta medida no equivale al rendimiento de la Mi TV física.
- Programa propio de Game Boy en modo móvil: autoarranque, cambio real del vídeo
  al pulsar A desde Android y salida mediante un menú Flutter con foco.
- Windows: Arkanoid, Barline (MAME 0.289) y Metal Slug con vídeo, teclado dirigido
  a su ventana, pausa, continuación y cierre. Los ZIP se alojan en una carpeta
  genérica de ROMs; MAME completo puede interpretar un directorio con nombre de
  máquina como una lista de software.

Los helpers son `tools/run_native_tv_test.py`, `tools/check_native_windows.py` y
`tools/run_tv_input_test.py --target integration_test/mobile_controls_test.dart`.
