# Revisión funcional · GameClub 0.13.5

## Controles y reutilización de texturas · 0.13.5

- El propietario aporta una foto de South Park renderizado en Switch y confirma
  sonido al introducir monedas. Pulsó +/START y la app salió; el log recibido es
  del siguiente intento y termina en `Loading Textures... 45%`, con caché previa.
- Se confirma un error de asignación del port: + estaba mapeado a Escape, cuya
  acción ExitGame cierra la mesa en standalone. El menú usa F12. Se corrigen
  controles/documentación: +/Y Start, B menú, X/− moneda, A lanzador.
- En la precarga con `used_textures.xml`, el worker mantenía `mutex` y volvía a
  bloquearlo dentro de ENABLE_OPENGL: bloqueo recursivo de un mutex no recursivo.
  Aunque se eliminara ese segundo lock, la subida OpenGL seguiría ejecutándose
  en un worker sin el contexto. Horizon ahora encola esas subidas y las ejecuta
  desde el hilo gráfico después de terminar la preparación CPU.
- Los bitmaps decodificados se retienen con AddPendingUpload hasta la subida;
  se respeta el flag lineal. Un worker limita el pico de memoria temporal. La
  cola valida su hilo propietario y no mantiene su mutex durante las callbacks.
- 18 regresiones nuevas: +/Y/B y resto del mapa, ausencia de Escape directo,
  cargas encoladas desde worker, envío solo por propietario, cola vacía, callback
  que encola más trabajo, rechazo de otro hilo conservando la cola, rotación de
  los dos logs previos y conservación de NVRAM/directorios ajenos. Total: 158.
- El primer log no se conserva en 0.13.4 al arrancar otra vez; por eso no permite
  afirmar si hubo además otro fallo. Desde 0.13.5 se guardan previous/previous2.
  **La nueva ruta de Start y el segundo arranque requieren otra prueba física.**

## Revisión anterior · 0.13.4

## Límite de GLSL del driver de Switch · 0.13.4

- El log nuevo de South Park es de 0.13.3. UI, Basic, Ball, DMD, Flasher y Light
  compilan en la consola; SMAA también termina compilando. El fallo de FBShader/AO
  indica literalmente que GLSL 4.50 no está soportado y enumera 4.30 como máximo.
- El shader de posprocesado de upstream declaraba `#version 450 core`. La
  comprobación anterior creó un contexto OpenGL 4.3 en NVIDIA, pero ese driver
  aceptó la versión de lenguaje superior; por tanto no reproducía ese límite.
- Preprocesado de Horizon compartido/probado para adaptar 450 a 430 core,
  conservar versiones inferiores y defines standalone. El empaquetado aplica
  el mismo límite y rechaza recursos que aún declaren una versión mayor.
- 72 regresiones GLFX, seis más de versión, sumadas a las otras 68: 140.
  Recorrido de carátulas y siete vistas del lanzador conservados.
- Validación estricta adicional con glslc del Android NDK, `-std=430core` y
  semántica OpenGL, sobre las 166 etapas de los 83 programas mono; compilación
  y enlace posterior en la GPU del PC. Cabeceras generadas verificadas <=430.
  Informe: `dist/switch-shader-gpu-0.13.4/report.json`. Esto comprueba el código
  GLSL y su límite de lenguaje, no el driver de Switch ni una mesa jugable.
- **Otra prueba física pendiente.** No se modifican los motores de PC/móvil/TV,
  salvo numeración 0.13.4+35, ni el servidor Raspberry.

## Revisión anterior · 0.13.3

## Lectura de shaders y sincronización · 0.13.3

- El registro físico de 0.13.2 confirma RGBA8888 aceptado y contexto OpenGL creado.
  Aparece un aviso de sincronización y los ocho archivos GLFX del reproductor
  informan de cero shaders. El log termina tras SMAA; no prueba una mesa jugable.
- Los recursos copiados de un checkout Windows tenían CRLF. `std::getline` en
  Horizon conservaba `\r`, generando claves como `TECHNIQUES\r`; la búsqueda de
  `TECHNIQUES` quedaba vacía. La comprobación antigua de stringstream aceptaba
  la cadena vacía y registraba cero compilaciones como éxito.
- Parser para Horizon separado y usado por motor/pruebas: lectura binaria,
  eliminación de CR/BOM, defines e includes con propagación de errores/límite
  de recursión. El motor rechaza explícitamente archivos sin técnicas. El
  empaquetado normaliza los shaders a LF y comprueba sus secciones de técnicas.
- 66 comprobaciones nuevas sobre los 10 GLFX reales y 94 técnicas. LF y CRLF
  producen mapas de secciones idénticos, con defines y funciones referenciadas.
  BOM, includes ausentes/malformados, recursión y técnicas ausentes comprobados.
- Prueba adicional mediante SDL3 y contexto OpenGL 4.3 oculto en Windows:
  83 programas mono compilados y enlazados en NVIDIA GeForce RTX 4060 Ti. Usa
  las secciones exportadas por el parser y la generación de fuentes correspondiente
  al backend standalone/mono. No prueba el driver de Switch, renderizado de una
  mesa, audio ni PinMAME. Informe: `dist/switch-shader-gpu-0.13.3/report.json`.
- Frame pacing convertido a VSync en Horizon antes de inicializar GL: el modo
  de escritorio carece de fuente DWM/DXGI en este sistema.
- El propietario confirma que la biblioteca ya navega fluida con 0.13.2.
  Se conservan sus correcciones. **Nueva prueba del motor en Switch pendiente.**

## Revisión anterior · 0.13.2

## Formato de pantalla y navegación · 0.13.2

- El nuevo log físico confirma `table loader workers joined`, carga de PinMAME
  y FlexDMD, dispositivos de audio iniciados y ventana 1280×720 creada. El fallo
  actual es `Invalid Output format: 373694468`, correspondiente a RGBA8888.
  El bloque OpenGL de VPX solo aceptaba ese formato al compilar para OpenGL ES.
- Adaptación de formato para Horizon probada con los enums reales de SDL3 y el
  valor literal del registro; se conservan precisión y canales RGB/RGBA/10 bits.
  Se rechazan formatos no admitidos. 9 comprobaciones de esta función.
- El propietario confirma que la lentitud aparece al recorrer páginas/cargar
  carátulas. La caché anterior expulsaba la primera clave alfabética, pudiendo
  descartar carátulas visibles y recargarlas en cada dibujo. Se sustituye por LRU;
  cuatro regresiones nuevas comprueban uso reciente, límite y liberación/limpieza.
- Descarga, consulta de SD, decodificación y escalado de carátulas ejecutados en
  el worker. El hilo gráfico solo crea texturas pequeñas y dibuja. Hasta cuatro
  cargas pendientes y 32 texturas; resultados negativos cacheados hasta recargar.
- Prueba de navegación con más de 32 carátulas, claves en orden inverso y vueltas
  a páginas residentes; incluye JPEG dañado y carátula ausente para detectar
  reintentos continuos. El informe registra trabajos, subidas y renderer. Los
  tiempos de escritorio no se presentan como FPS de Switch.
- Resultado del recorrido de 480 frames: 40 trabajos, 38 imágenes válidas subidas
  y 32 texturas residentes; sin recargas al volver a las páginas conservadas.
  La imagen dañada se solicita una vez y la ausente no genera petición HTTP.
- 51 comprobaciones del cliente, 8 de hilos y 9 de formato, más siete vistas y
  la navegación de estrés. **Otra prueba física sigue pendiente:** el formato
  corregido aún no certifica imagen, audio de juego, emulación ni rendimiento.

## Revisión anterior · 0.13.1

## Corrección de cierre durante la carga · 0.13.1

- El log del propietario confirma VPX iniciado y Fish Tales abierto. Entre
  `PinTable Data loaded` e `Images, Sounds and Items loaded` transcurren unos
  cuatro minutos. Después registra resolución de capas y termina antes de
  `InitTablePostLoad`; todavía no hay evidencia de renderizado ni de PinMAME en
  ejecución.
- El grupo de hilos original llama a `std::thread::detach()` al destruirse justo
  después de resolver las colecciones. Desensamblado del ELF anterior: ese método
  llama a `pthread_detach`, cuyo backend devuelve incondicionalmente ENOSYS (88).
  La excepción sin capturar en el hilo encaja con ese punto de interrupción.
- Grupo de hilos Horizon corregido para conservar handles y hacer `join` desde
  el propietario. Crecimiento/reducción serializados; no se descarta trabajo.
  El renderizador standalone actualiza su contador en línea sin otro `detach`.
- 8 regresiones de la rama Horizon comprobadas en escritorio, además de las
  47 del lanzador. La prueba compila sin permitir llamadas a `detach`; comprueba
  trabajo pendiente, futuros, excepciones, cambios de tamaño y fin de hilos/TLS.
  El ELF nuevo no enlaza `std::thread::detach()`.
- Corregida la fuga del búfer de píxeles al importar imágenes BITS antiguas y
  comprobados errores de FreeImage. Excepciones de motor registradas y limpieza
  SDL al salir. Se elimina la inicialización de sockets del motor local.
- La foto muestra 2162-0002 / programa 0100000000000012, servicio `bsdsocket`.
  No hay informe de ese servicio que permita afirmar la causa del fatal posterior.
  **Nueva prueba en Switch pendiente; no se certifica todavía una mesa jugable.**

## Revisión anterior · 0.13.0

## Port Visual Pinball/PinMAME para Switch · 0.13.0

- Fuentes VPX/PinMAME, SDL3/libnx, Wine VBScript, FreeImage, B2S y FlexDMD
  compiladas para AArch64. Enlace estático y NRO0 con icono/NACP/versión
  comprobados por `tools/package_switch_pinball.py`.
- 47 comprobaciones nativas superadas. Las nuevas cubren preparación de mesa y
  ROM desde el manifiesto, CRC incorrecto, traversal, motor ausente, argumentos
  nativos y NVRAM estable. También comprueban progreso durante archivos grandes,
  cancelación a mitad de extracción, limpieza y reintento conservando la descarga.
  Los paquetes de prueba son fixtures propios, no juegos.
- Preparación local de South Park (Sega), con el mismo código HTTP/miniz del
  lanzador contra la Raspberry: descarga de 67.600.224 bytes y extracción de la
  mesa de 82.911.232 bytes completadas. Esta prueba se ejecuta en Windows y no
  certifica velocidad de SD ni ejecución del motor en Switch.
- Siete vistas del lanzador renderizadas, incluida la ficha de pinball. Análisis Flutter limpio y 47 pruebas
  superadas; el cambio de Flutter en esta versión solo actualiza la numeración.
- SDK y dependencias fijados por SHA-256/revisión, parches idempotentes y
  preparación reproducible comprobada. No se instala el SDK globalmente ni se
  cambian ROMs, paquetes o configuración del servidor Raspberry.
- **Primera prueba física fallida:** el propietario confirma que GameClub abre,
  pero comunica descarga lenta y bloqueo antes de jugar al pinball. La revisión
  añade búferes de escritura, fases/progreso, cancelación y registros de apertura.
  La segunda prueba sigue pendiente: vídeo, audio, mandos, emulación efectiva y
  compatibilidad/rendimiento de mesas no están certificados.

## Revisión anterior · 0.12.0

## NRO para Switch · 0.12.0

- Compilación cruzada C++17 con devkitA64 r30/GCC 16.1.0 y libnx 4.12.0. ELF
  de 64 bits, máquina AArch64, cabecera NRO0, NACP con título/versión, icono y
  RomFS con las tres tipografías gráficas y avisos de terceros comprobados.
- **33 comprobaciones nativas superadas**, con una API HTTP aislada y fixtures
  propios: autenticación y 401; catálogo/favoritos; URLs y rutas inválidas;
  aislamiento por servidor; caché y revisión; descarga truncada sin publicar;
  encabezados NRO inválidos; dependencias MAME y traversal rechazado; rutas de
  batería estables para otras consolas y sesiones nuevas para NES/MAME/Atari.
  Se conservan carpetas ajenas y guardados al limpiar sesiones marcadas.
- Seis vistas del mismo código SDL2 renderizadas en escritorio: biblioteca,
  favoritos, consolas, ajustes, ficha y búsqueda. También se consulta la API
  real de la Raspberry y se renderizan sus carátulas. No se modifican sus juegos.
- **47 pruebas Flutter superadas y análisis sin incidencias.** Builds Windows,
  móvil y TV 0.12.0+30. Se conserva el servidor desplegado 0.10.3.
- **Sin prueba en Switch física:** no se certifican todavía el arranque desde
  Homebrew Menu, Wi-Fi/teclado/Joy-Con reales, apertura de RetroArch o rendimiento
  de cada núcleo. Los tests del lanzador comprueban preparación y argumentos;
  no ejecutan esos núcleos ni presentan los fixtures como juegos emulados.

## Revisión anterior · 0.11.0

## Biblioteca retro · 0.11.0

- **47 pruebas Flutter superadas y análisis sin incidencias.** Se conservan las
  regresiones de guardados, variantes, carátulas y mando. Siete pruebas nuevas
  recorren biblioteca, ficha, favoritos y ajustes a 320×568, 390×844, 844×390,
  1440×1000, TV 962×541, móvil con mando y texto ampliado al 150%.
- Se comprueba que la primera ficha cabe en la cuadrícula; se carga la fuente
  pixelada real. Ventanas bajas con teclado, mensajes vacíos desplazables y
  selectores largos conservan sus acciones sin desbordamientos.
- Regresión específica de giro con barras del sistema: el buscador conserva su
  texto y filtro, y las fichas cambian a disposición horizontal en vistas bajas.
- Windows release revisado con la biblioteca real de la Raspberry: carátulas,
  filtros y ficha con portada/capturas. El backend permanece en **0.10.3**.
- Compilaciones Windows, móvil y TV **0.11.0+29**. Auditoría de hashes de motores
  y recursos VPX originales: móvil conserva el motor, TV lo excluye. AAPT verifica
  versión/código, paquete, API mínima 24, tres ABI y lanzador de cada variante.
- Fuente Press Start 2P y licencia OFL completas comprobadas en las tres apps.
  El cambio afecta a presentación y navegación de biblioteca; las pruebas de
  ejecución de motores de 0.10.4 se documentan abajo como antecedentes.
- Los APK móvil y TV finales se instalaron en un AVD aislado Android 36.1
  x86_64: biblioteca real, búsqueda de 1942, ficha/capturas, favoritos y ajustes.
  Móvil conserva texto y filtro al girar y muestra títulos completos. TV recorre
  pestañas con RB, enfoca con Select y abre la ficha con cruceta/A; se esperan
  los cambios de foco entre pulsaciones. Capturas locales en
  `dist/retro-release-0.11.0/`; banco: `tools/check_retro_release.py`.
  No se trata de una prueba nueva en el móvil o televisor físicos.

## Revisión anterior · 0.10.4

## Salida y partidas por sistema · 0.10.4

- **39 pruebas Flutter**: política MAME/NES/Atari/VPX sin persistencia; menú
  Salir frente al menú con guardado de Nintendo DS; rechazo de restauración
  de batería antigua y descarte de nuevos autosaves arcade; Nintendo DS conserva
  escritura, lectura y sobrescritura de su batería mediante la API local.
- **Tres pruebas C++**: diseño táctil, mandos y almacenamiento de sesión.
  Esta última verifica sesiones nuevas y simultáneas aisladas, eliminación de
  NVRAM/estados temporales al salir y preservación de un archivo antiguo ignorado.
- Windows release: Super Mario Bros., Super Mario Bros. 3 y Pac-Man Atari
  NTSC/PAL con vídeo, audio, controles, menú y salida comprobados. El banco
  introduce una batería antigua, comprueba que no se sobrescribe y exige que
  no queden archivos de sesión. También pasa el banco MAME con Arkanoid.
- Android TV en AVD: MAME Arkanoid con vídeo, entradas, ejes, menú, continuación,
  salida y segundo arranque. En ambos cierres se comprueban la batería antigua
  sin modificar y la carpeta de sesiones vacía.
- APK móvil release ARM64: Attack from Mars, menú **Salir**, continuación,
  reinicio y vuelta a la biblioteca. La NVRAM/configuración de PinMAME se conserva;
  el puente carga/enciende la mesa en cada apertura sin restaurar un estado.
- El modo web MAME deja de exportar/restaurar NVRAM y estados; el modo arcade
  EmulatorJS no monta IDBFS y usa nombres de sesión independientes. El endpoint
  local ignora autosaves antiguos y no entrega guardados a esas sesiones.
- Compilaciones Windows, móvil y TV 0.10.4 (código Android 28), con análisis
  limpio, recursos/hashes auditados y comprobación AAPT de ambas variantes.
  La política se aplica en el cliente y sirve con el servidor 0.10.3 desplegado.

## Revisión anterior · 0.10.3

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
