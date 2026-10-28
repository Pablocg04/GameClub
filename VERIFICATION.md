# Revisión funcional · GameClub 0.10.3

## Imágenes Visual Pinball / PinMAME · 0.10.3

- **90 pruebas Python superadas.** Regresiones de migración de un índice v2,
  selección de folleto frontal, nombres `r2_`, exclusión de rutas inválidas,
  capturas sin carátula, descarga 404, deduplicación, plataforma correcta,
  limpieza de títulos y rechazo de secuelas ambiguas.
- API autenticada: búsqueda/asignación de carátula, capturas LaunchBox servidas
  como JPEG, repetición sin duplicados e invalidación de la caché antigua vacía.
- Descargas reales verificadas como imágenes válidas: Attack from Mars (folleto
  y dos capturas), Medieval Madness (folleto y una captura), Black Knight 2000
  (folleto y una captura).
- Índice público reconstruido: 3748 recursos de carátula y 2899 capturas en
  Pinball. LaunchBox usa esquema v3; los otros índices mantienen v2.
- Servidor **0.10.3 desplegado en la Raspberry**, con índice precargado. Comprobadas
  las carátulas y 18 capturas de las 14 mesas existentes mediante la API real,
  incluida la descarga y validación de cada imagen. Solo se asignan carátulas
  ausentes; se conservan las imágenes anteriores. No se suben ROMs.
- La corrección del servidor es compatible con los clientes anteriores.
- **35 pruebas Flutter superadas y análisis limpio.** Compilaciones release
  Windows, móvil y TV 0.10.3 (Android código 27). Los paquetes verifican recursos
  y hashes de motores; AAPT comprueba identidad, versión, ABI y variante TV.
  TV sigue excluyendo VPX.

## Revisión anterior · 0.10.2

## Encuadre, marcador y audio VPX móvil · 0.10.2

- **35 pruebas Flutter superadas y análisis limpio.** Compilaciones release de
  Windows, Android móvil y TV (versión 0.10.2, código Android 26).
- Ejecutado el APK móvil release en el AVD Android 36 con traducción ARM64,
  tanto con la mesa oficial de ejemplo como con Attack from Mars g5k 1.3.11,
  ROM hija `afm_113b` y padre `afm_113`.
- Mesa, controles táctiles, flipper mantenido, menú por mando, continuación,
  reinicio en el mismo proceso y salida a la biblioteca comprobados.
- El banco de ajustes cambia el volumen mecánico y desactiva ScoreView;
  aplica/reinicia y vuelve a abrir el diálogo para comprobar la persistencia.
  En debug se verifica además el INI del motor: SoundVolume, MusicVolume,
  BGSet, ViewCabMode y ScoreViewOutput. El APK release se prueba también
  actualizando la instalación debug, conservando sus datos.
- Attack from Mars presenta un solo DMD al usar la vista de mueble con
  ScoreView activo. Se comprueba también la desactivación del adicional.
- Al girar, VPX conserva la proporción de proyección inicial: se detectó que
  expandir la superficie a toda la pantalla deformaba la mesa hasta reiniciarla.
  La superficie ahora mantiene proporción 3:5, centrada dentro del área libre
  de controles; se verifican giro, imagen sin estirar, menú y reinicio horizontal.
  No se reinicia la partida al girar.
- PinMAME inicializa su flujo mono INT16 a 44.1 kHz. Su código fijado publica
  audio BACKGLASS; VPX aplica MusicVolume a ese canal y SoundVolume al playfield.
  Mecánica inicial 35%, electrónica/música 100%, modificables por mesa.
- La comprobación visual y de canales en el emulador no sustituye la escucha
  del balance ni la comprobación de rendimiento en el Snapdragon físico.
- Los paquetes se auditan con sus hashes y los dos APK con AAPT; TV sigue
  excluyendo recursos y bibliotecas de VPX.

## Revisión anterior · 0.10.1

## Catálogo y APK TV sin Visual Pinball · 0.10.1

- La variante TV filtra el sistema VPX y sus mesas al cargar biblioteca y
  favoritos; por ello tampoco aparecen en filtros ni selectores de subida,
  aunque se active Mostrar consolas vacías.
- La política depende de la variante del APK, no de la navegación por mando:
  el móvil mantiene VPX al conectar un controlador.
- Pruebas de interfaz con un servidor que devuelve juegos MAME y VPX a la vez:
  TV conserva Pinball Action y oculta Attack from Mars; móvil conserva ambos.
- **35 pruebas Flutter superadas y análisis limpio.** Compilaciones release de
  PC, móvil y TV. El APK TV pasa de aproximadamente 302 MiB a 74 MiB al excluir
  las bibliotecas y recursos de VPX; móvil mantiene su motor integrado.
- El empaquetado verifica que TV no contiene bibliotecas ni recursos VPX, y
  que los originales de móvil siguen coincidiendo con sus SHA-256 fijados.

## Revisión anterior · 0.10.0

## VPX Android integrado · 0.10.0

- Se incorpora la API C de la biblioteca oficial `libvpinball.so`, sus
  dependencias ARM64 y sus recursos. El APK original se usa como distribución
  verificable; no se instala ni se abre como aplicación externa.
- El motor se ha ejecutado realmente dentro de `com.gameclub.gameclub:pinball`,
  con una mesa oficial de ejemplo, en un AVD Android 36 con traducción ARM64.
  Backend Vulkan, carga de scripts, inicialización de audio, física y vídeo 3D comprobados.
- Flipper izquierdo táctil mantenido y movimiento visible; controles reservan
  área fuera de la superficie de juego. Menú con Start + Select, B continúa,
  Atrás abre menú y Guardar/salir devuelve la biblioteca.
- Los guardados y preferencias permanecen dentro de la app por servidor/juego.
  El proceso se cierra después del evento nativo de guardado y cierre.
- Se detectó y corrigió la selección táctil del menú que inicialmente solo
  enfocaba un botón en el primer toque.
- La primera prerenderización del emulador por software fue lenta; se ajustó
  el plazo de carga y se comprobó con GPU del host. Esta prueba no garantiza
  FPS en el Snapdragon ni sustituye la comprobación en un móvil/TV físico.
- **87 pruebas Python, 33 Flutter y tres comprobaciones del canal Android
  superadas**, además del banco de reproducción ARM64 descrito. Análisis limpio.
  Los dos APK release incorporan las bibliotecas/recursos originales: sus SHA-256
  se comprueban durante la compilación y al preparar los paquetes finales.
- Comprobados también los **APK release finales móvil y TV**, forzando el ABI
  ARM64 en el mismo AVD: mesa 3D, controles/mando, pausa, continuación y salida.
  En la variante TV se comprueba que no exista botonera táctil y se reinicia
  la mesa dentro del mismo proceso antes de guardar y volver a la biblioteca.

## Revisión anterior · 0.9.1

## Corrección pinball Windows · 0.9.1

Se reprodujo en los registros del usuario el arranque de VPX sin recibir foco:
la mesa cargaba, pero no aparecía `Unpausing Game`. El banco anterior forzaba el
foco al capturar la ventana y ocultaba ese fallo. La comprobación actual exige
que lo adquiera el propio reproductor.

El host Windows incorpora mando SDL, menú Start + Select / Esc, continuar,
reiniciar y salida guardando. El banco `tools/check_pinball_controls.py` usa
un mando SDL virtual, una carpeta de prueba nueva y NVRAM sin datos previos;
comprueba el movimiento visible de ambos flippers, los créditos, la liberación
al pausar/desconectar y la reapertura. No captura otras ventanas ni modifica
las mesas originales.

La configuración de vídeo/audio y las partidas se conservan al migrar los
controles. La versión del servidor continúa en 0.9.0: este cambio es del cliente.

Resultado: **33 pruebas Flutter**, análisis limpio, banco del host **release**
desde cero con movimiento visual de flippers y banco Flutter → host → VPX
completos. Ambos bancos comprueban el menú y la salida guardando sin forzar el
foco desde las herramientas de captura. APKs móvil y TV 0.9.1/23 compilados.

## Revisión anterior · 0.9.0

## Visual Pinball · 0.9.0

- **87 pruebas Python y 32 Flutter superadas**, análisis Flutter limpio.
- Validación de paquete por mesa, OLE/BIFF, detección de ROM, rutas, dependencias,
  subida/descarga autenticadas y filtro MAME.
- Extracción de mesa y ROMs, conservación de NVRAM y exportación VPXZ.
- **Attack from Mars g5k 1.3.11 en Windows**: paquete completo preparado por
  GameClub; motor VPX BGFX fijado por SHA-256, ROM `afm_113b` con padre `afm_113`,
  texturas, física, audio, panel B2S, créditos, partida, bola, puntuación y ambos
  flippers comprobados. Salida a GameClub y reapertura conservando NVRAM.
- La primera inicialización muestra `Factory settings restored`; salir y volver
  a abrir completa el arranque. La mesa incluye un marcador propio además de
  ScoreView: se puede desactivar o recolocar este último en los ajustes VPX.
- Compilaciones release Windows, móvil y TV; APKs 0.9.0/22 con los tres ABI,
  lanzadores diferenciados y FileProvider pinball no exportado.
- Tres comprobaciones de integración Android: requisito de VPX oficial antes de
  descargar, rechazo de archivos ajenos a la carpeta de exportación y generación
  del URI FileProvider de un VPXZ válido hasta detectar la app ausente. El AVD
  x86_64 anuncia también ARM64 por traducción; esta prueba no ejecuta el motor VPX.
- VPX Android ARM64 físico sigue pendiente. La entrega Android requiere la app
  oficial externa y confirmación de importación.
- **Raspberry desplegada en 0.9.0**: API y sistema VPX disponibles; descarga real
  del motor de 212 800 616 bytes con SHA-256 correcto y siete pinballs MAME
  reconocidos por el filtro. Índices de carátulas precargados (2 358 mesas en
  LaunchBox). El despliegue no transfiere mesas ni ROMs del escritorio.

Guía y banco reproducible: [PINBALL.md](PINBALL.md).

## Revisión anterior · 0.8.1

## Fallos reproducidos y corregidos

1. **ROM sustituida por otra del mismo tamaño:** la copia local no se invalidaba.
   El escaneo publica una revisión basada en la modificación del archivo y la
   caché comprueba esa revisión, además del tamaño.
2. **Mismo identificador de juego en dos servidores:** la descarga general podía
   reutilizar el archivo de otra biblioteca. Ahora se separa por servidor.
3. **Teclado en una ventana baja:** la biblioteca y la búsqueda de carátulas podían
   desbordarse. Los diálogos son desplazables y los filtros se ocultan mientras
   está abierto el teclado.
4. **Caché de catálogo incompleta:** un SQLite sin tablas o un ZIP incompleto podía
   impedir la búsqueda. Se valida su estructura y se reconstruye cuando falla.
5. **NDS móvil:** el dedo llegaba al canvas, pero DeSmuME no recibía el lápiz. El
   adaptador traduce el contacto a los eventos de ratón que admite el motor web,
   incluyendo soltar, cancelar, perder el foco y abrir el menú.
6. **Preparación inicial de catálogos:** la búsqueda individual podía agotar los
   90 segundos del cliente. Esa operación dispone de un plazo específico mayor.

Los cambios conservan favoritos, títulos, imágenes y las rutas de guardados.

## Comprobaciones realizadas

Resultado: **75 pruebas Python, 29 pruebas Flutter y dos pruebas C++ superadas**,
además de los bancos de integración indicados a continuación. Análisis Flutter limpio.

- Pruebas del servidor: biblioteca, autenticación, subida, escaneo, descarga,
  persistencia, metadatos, imágenes manuales, capturas, scrape, cancelación,
  reanudación, fuentes encadenadas, ZIPs, BIOS, padres, CHD y motores nativos.
- Pruebas Flutter: biblioteca, filtros, búsqueda, favoritos, ajustes, subida de
  lotes, imágenes, menú, cachés, verificación de motores y liberación de mandos.
- Dos bancos C++ de ejes y geometría de controles táctiles.
- **Windows:** NDS, GB, GBC, GBA y SNES con programas gráficos propios; botón A,
  cierre y reapertura, y conservación real de SRAM en GB.
- **Windows arcade:** Arkanoid/MAME 2003-Plus, Barline/MAME completo y Metal
  Slug/FBNeo: vídeo, teclado dirigido, pausa, continuación y cierre.
- **Móvil Android 36.1 emulado:** los cinco motores web, toque y liberación del
  lápiz NDS, botón A, cierre y SRAM; NES con rotación real vertical/horizontal;
  Atari 2600 con botones táctiles; menú y segunda apertura de las dos consolas.
- **Google TV Android 36 emulado:** Arkanoid y Metal Slug nativos, botones,
  ejes, pausa, continuación, cierre y segunda apertura.
- **APKs release 0.8.1:** ajustes y resultados reales de carátulas en teléfono y
  TV; Arkanoid abierto desde la biblioteca TV, salida y recuperación de LB/RB,
  Select y teclado. El banco espera que termine Guardar/conectar antes de enviar
  atajos, evitando confundir Biblioteca con Favoritos.

Las ROMs comerciales usadas para los bancos locales permanecen fuera del código
publicado. Los programas propios se generan desde `tools/fixtures/` y
`tools/player_fixture.py`; no se publican sus archivos ROM compilados.

## Repetir los bancos

```powershell
python -m pytest server/tests -q
# Desde client:
flutter analyze
flutter test
# Desde la raíz, con las rutas de Flutter y LLVM/NDK de tu equipo:
python tools/run_player_tests.py --flutter <flutter.bat> --platform windows --llvm <llvm-bin> --root <carpeta-temporal>
python tools/run_player_tests.py --flutter <flutter.bat> --platform android --device <emulator-id> --llvm <llvm-bin> --root <carpeta-temporal>
python tools/check_publication.py
```

La integración completa necesita Windows/Android SDK, los motores correspondientes
y una red accesible para las descargas iniciales. N64 y los emuladores externos no
se han probado con juegos reales en esta revisión. Las pruebas emuladas tampoco
equivalen a probar la TV y los mandos Bluetooth físicos del propietario.
