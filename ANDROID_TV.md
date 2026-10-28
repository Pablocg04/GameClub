# GameClub para Android TV / Google TV · 0.10.2

## APK específico para televisión

Instala **`dist/android-tv-0.10.2/GameClub-AndroidTV.apk`**. Esta variante fuerza el
modo TV y la orientación horizontal, incluye launcher Leanback y banner, y utiliza
mandos sin controles táctiles sobre el juego. La versión es **0.10.2**, código **26**.

Para teléfono/tablet utiliza **`dist/android-mobile-0.10.2/GameClub-Android.apk`**:
controles más grandes, estilo clásico y orientación automática/vertical/horizontal.
Consulta [ANDROID_MOBILE.md](ANDROID_MOBILE.md).

Desde 0.10.1 **Visual Pinball no aparece en el APK TV**: se ocultan el sistema,
las mesas, los favoritos y el selector de subida, y se excluye su motor del
paquete. PC y móvil conservan VPX. Los pinballs MAME mantienen su ruta nativa
anterior y siguen disponibles en TV.
Consulta [PINBALL.md](PINBALL.md).

Las carátulas se buscan en Libretro → LaunchBox → GameTDB, con subida manual como
alternativa. No requieren cuenta ni claves. Consulta [THUMBNAILS.md](THUMBNAILS.md).

NES y Atari 2600 se ejecutan nativamente con Nestopia UE y Stella, incluidos en
el APK. Comprobadas ambas en Google TV emulado con vídeo, audio, botones, ejes,
menú y segundo arranque. El APK release también se ha abierto desde la biblioteca
normal con Pac-Man Atari. Detalles: [NATIVE_CONSOLES.md](NATIVE_CONSOLES.md).

Ambos APK actualizan el paquete anterior conservando sus datos. Son alternativas
según el dispositivo, compiladas desde una misma base de código. Para desarrollo:
`flutter build apk --release --flavor tv` o `--flavor mobile`.

## Referencia de la versión 0.6.0

### Instalación de referencia (0.6.0)

Instala `dist/android-tv-0.6.0/GameClub-AndroidTV.apk` sobre la versión anterior.
Es el mismo APK para móvil y TV: Android 7/API 24+, ARM32/ARM64/x86_64,
versión **0.6.0**, código **15**. Servidor: `http://192.168.0.47:8001`.

- Arcade abre un motor **nativo SDL/libretro**, sin WebView, a pantalla completa.
- Todos los sistemas integrados arrancan al abrirlos; no hay segundo botón de inicio.
- **Start + Select / Mode / Atrás** abre el menú; cruceta selecciona y **A/OK**
  confirma. **B/Atrás** continúa. Elige **Guardar y salir** para cerrar.
- **LB/RB o L1/R1** cambia pestañas; **Select** abre búsqueda y teclado.
- En móvil, conectar/desconectar un mando actualiza el modo de navegación sin reiniciar.
- Arcade móvil tiene cruceta con diagonales y botones A/B/X/Y, L/R y Select/Start.

La prueba nativa comprobó Arkanoid, Metal Slug, Barline, Casino Fever 6.1 y Royal
Casino en Google TV emulado, incluidos mandos, controles táctiles, menú y nueva
apertura. La ruta de consola también se comprobó en modo móvil con un programa
propio que cambia la imagen al pulsar A. Detalles: [MAME_NATIVE.md](MAME_NATIVE.md).

Los ajustes antiguos de composición/rAF solo afectan a los motores de consola;
MAME nativo no los utiliza. La velocidad real en la Mi TV y el emparejamiento
Bluetooth físico requieren la comprobación en ese equipo.

## Histórico de instalación y diagnóstico · 0.5.3

Los apartados siguientes describen la versión anterior y sus medidas de WebView.

### Instalar y conectar el mando (0.5.3)

1. Copia `dist/android-tv-0.5.3/GameClub-AndroidTV.apk` al televisor, por USB o
   mediante una aplicación de transferencia de archivos, e instálalo.
2. En los ajustes de **Mandos y accesorios / Bluetooth** de la tele, empareja
   el mando de juegos. El nombre del apartado varía según el fabricante.
3. Abre **GameClub** desde el lanzador de Android TV. Detecta el modo televisión
   y muestra la biblioteca con foco visible y navegación por cruceta.
4. Conecta con `http://192.168.0.47:8001` desde **Ajustes** si no aparece ya.
   La tele debe poder acceder a esa dirección en la red local.
5. Selecciona un juego y pulsa **Jugar en GameClub**. En televisión, los sistemas
   integrados arrancan automáticamente y no muestran la botonera táctil.

También hay un acceso a los ajustes Bluetooth desde los ajustes de GameClub.
El emparejamiento lo hace Android; la app recibe los eventos del mando conectado.

## Controles

| Acción | Control |
|---|---|
| Moverse por la biblioteca | Cruceta; stick izquierdo del mando de juegos |
| Seleccionar / abrir | OK del mando de la tele o A del mando de juegos |
| Volver desde una ficha | Atrás de la tele o B del mando de juegos |
| Cambiar entre Biblioteca, Favoritos y Ajustes | LB/RB de Xbox; L1/R1 de PlayStation, con recorrido circular |
| Buscar en Biblioteca o Favoritos y mostrar el teclado Android | Select del mando (botón View en Xbox, según el mapeo Android) |
| Abrir el menú durante el juego | Start + Select; también botón Mode si Android lo entrega |
| Cerrar guardando | Atrás de la tele, o **Guardar y volver a la biblioteca** en el menú |
| Moneda e inicio en arcade | Select y Start |

Dentro del juego, B corresponde al botón de juego y no vuelve a la biblioteca.
El menú permite pausar y continuar. Android conserva la ruta de cada pulsación
al abrir/cerrar el menú para no dejar teclas retenidas. Al desconectar un mando,
perder el foco o pasar a segundo plano se liberan sus entradas.
Desde 0.5.3, el cierre espera la liberación nativa, detiene la página del reproductor
y devuelve el foco a Flutter antes de navegar por la biblioteca. Las liberaciones
tardías de una partida anterior no desactivan la captura de una nueva.
Los atajos de pestañas/búsqueda solo actúan en la biblioteca; las fichas y partidas
conservan sus controles propios.

Los botones A/B/X/Y, gatillos, hombros, cruceta y sticks se adaptan desde los
eventos estándar de Android al Retropad del motor. El stick izquierdo también
actúa como cruceta en los sistemas 2D; N64 recibe sus ejes analógicos.
Los nombres de los botones y su posición física pueden variar entre mandos.

Esta adaptación está destinada a los motores integrados de GameClub. Los
emuladores externos conservan sus propias pantallas y configuración de mandos.

## APK

Es un APK universal para Android y Android TV: incluye lanzador Leanback y banner,
y declara que no necesita pantalla táctil. Detecta televisión mediante UiModeManager
y la característica Leanback. La versión es **0.5.3**, código **14**.
Requiere Android 7.0 / API 24 o posterior e incluye ARM de 32/64 bits y x86_64.

```text
dist/android-tv-0.5.3/GameClub-AndroidTV.apk
client/build/app/outputs/flutter-apk/app-release.apk
```

Las partidas siguen siendo locales al dispositivo donde se juega; emparejar el
mismo mando en PC, móvil y tele no sincroniza las partidas entre esos equipos.

## Verificación

- 18 pruebas unitarias/de interfaz correctas y análisis Flutter sin incidencias.
- Navegación por una biblioteca de 80 juegos con cruceta, desplazamiento de filas
  fuera de pantalla, apertura con A y regreso con B.
- Google TV API 36 en emulador: detección automática, Street Fighter II con
  vídeo real, autoarranque sin tocar la pantalla, botones y eje de joystick
  introducidos mediante ADB y recibidos por la actividad Android nativa.
- Menú con Start + Select, continuación con A y salida guardando mediante Atrás.
- Desconexión sin volver a aplicar ejes pendientes, y limpieza al abrir el menú.
- 0.5.3: Arkanoid con MAME 2003-Plus en Google TV API 36 emulado: entrada nativa,
  menú/continuación, salida guardando y captura nativa inactiva al volver.
  Después de salir, RB abre Favoritos, LB vuelve a Biblioteca y Select muestra
  el teclado Android (visibilidad comprobada mediante ADB); la búsqueda recibe texto.
- Cierre idempotente: espera la confirmación nativa antes de cancelar el canal,
  y no permite reactivar una instancia ya cerrada.
- APK **release 0.5.3** instalado en el mismo AVD: búsqueda de Arkanoid con Select,
  apertura desde su ficha por A, vídeo con contador de emulación, salida con Atrás,
  cambio hasta Ajustes con RB y regreso/búsqueda con LB y Select. Comprobado por
  ADB/UI Automator con `tools/check_tv_release.py`, usando la navegación normal.
- Queda comprobar el emparejamiento y el perfil concreto de un mando Bluetooth
  físico en la tele del usuario.

## Rendimiento en televisores modestos

### Diagnóstico 0.5.3

El vídeo `demo.mp4` de la MiTV-MOOQ0 muestra aproximadamente **21–22 FPS de
emulación y 60 FPS WebView** usando MAME 2003-Plus. El segundo contador no demuestra
que el motor esté emulando a 60 FPS.

**Sincronizar motor con WebView (rAF)** está activado por defecto en 0.5.3.
Desactivarlo conserva el bucle inmediato de 0.5.2. Cierra y abre el juego después
de cambiarlo; compara el mismo juego y los dos contadores. Es una alternativa de
temporización, no una aceleración garantizada.

En el AVD Google TV API 36 x86_64 (GPU por software, WebView 143), con Arkanoid y
MAME 2003-Plus se midieron muestras de seis segundos tras dos de estabilización:

| Temporización | FPS emulación | FPS WebView |
|---|---:|---:|
| rAF, primera muestra | 34,3 | 59,9 |
| Bucle inmediato | 37,5 | 60,1 |
| rAF, segunda muestra | 35,3 | 60,1 |

La comparación **no mostró mejora con rAF en ese emulador** y no mide el rendimiento
de la Mi TV física. MAME 2003 también pasó la auditoría del ZIP, pero su motor web
falló al arrancar con `RuntimeError: unreachable`; no se ha elegido como sustituto
de Plus. FBNeo requiere un chip MCU que ese ZIP no contiene. No se ha demostrado
todavía una solución al límite de unos 20 FPS en el televisor del usuario.

0.5.2 añade **Composición directa del reproductor** para probar la vista Android
sin la ruta de textura usada previamente. Está activada por defecto en TV y se
puede desactivar para comparar el mismo juego o si la imagen falla.
Los contadores distinguen FPS de emulación y cadencia de callbacks rAF del WebView;
esta última no mide por sí sola los fotogramas físicos presentados por el panel.

## Navegación sin quedar atrapado en la cuadrícula

- Desde el borde izquierdo de los juegos, **Izquierda** lleva al menú inferior.
- **B** del mando de juegos también lleva al menú; no hace falta bajar hasta el
  último juego de una biblioteca grande.
- En el menú, **Izquierda/Derecha** recorren Biblioteca, Favoritos y Ajustes;
  **A/OK** abre el apartado.
- **Arriba** desde el menú devuelve el foco a los juegos o al primer ajuste de TV.
- **Arriba** desde la primera fila de juegos lleva a los filtros.
- En una ficha, B vuelve a los juegos; durante una partida B conserva su función
  de juego y Start + Select abre el menú del reproductor.

Se ha probado el recorrido juegos → Favoritos → Ajustes → interruptor de
rendimiento → menú, con cruceta y A/B, sin eventos táctiles.

## Perfil rápido

Desde 0.5.1, **Ajustes → Rendimiento rápido para TV** está activado por defecto.
El cambio se aplica al cerrar y volver a abrir el juego.

- El WebView del reproductor se dibuja en una superficie lógica de 640×360 y se
  escala para mostrarlo en la tele, en vez de rasterizar toda su resolución.
- Se solicita un modo de 60 Hz de hasta 1080p si Android lo expone. Si no existe,
  se solicita la frecuencia compatible sin forzar un modo no anunciado.
- EmulatorJS permite elegir rAF o bucle inmediato al arrancar; el perfil rápido
  evita suavizado y ajusta el búfer de audio.
- MAME web usa salto de dos fotogramas de vídeo, audio de 22.050 Hz y muestra su
  contador de rendimiento nativo. No se utiliza cámara rápida para simular una mejora.
- Los otros motores muestran fotogramas de emulación/s. Fuera de NDS ese número
  no se convierte en porcentaje, porque hay juegos de 50 Hz y otras frecuencias.
- Se puede desactivar el perfil para volver a la presentación equilibrada.

Las pruebas en Google TV emulado confirmaron una salida MAME de 640×359, frente
a 961×484 antes del perfil, y funcionamiento de mandos, pausa y guardado.
Esto verifica la reducción de carga y el funcionamiento, no mide la velocidad de
una Mi TV física ni garantiza el 100 % en todos los juegos. En Ajustes se muestra
la frecuencia de pantalla y la versión de WebView para diagnosticar ese equipo.

La versión 0.5.0 añade [MAME_WEB.md](MAME_WEB.md) para Barline, Casino Fever 6.1 y
Royal Casino, con autoarranque, menú, controles y guardados comprobados en Google TV emulado.

## Desarrollo

Los archivos Android reproducibles están en `client/platform-config/` y se
instalan en la plataforma generada mediante `client/bootstrap.ps1`.

`tools/prepare_tv_emulator.py` crea un AVD Google TV aislado en la carpeta temporal
indicada. `tools/run_tv_input_test.py` ejecuta la prueba de integración e introduce
eventos de mando mediante ADB. Usa `flutter drive --no-dds` para evitar un problema
del listener de golden tests de Flutter 3.47 al ejecutar `flutter test` en ese emulador.

El helper acepta `--game arkanoid.zip --compare-timing` para medir rAF/inmediato/rAF
y `--core` para elegir un candidato previamente auditado por el servidor.
`tools/check_tv_release.py --adb <ruta-a-adb>` comprueba el APK ya instalado desde
su biblioteca normal, sin el ejecutor de integración Flutter.
