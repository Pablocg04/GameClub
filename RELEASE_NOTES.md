# GameClub 0.13.6

- El propietario confirma South Park funcionando con 0.13.5. El registro llega
  a Startup done, recibe Start y no muestra un cierre; B pausa/reanuda. Reporta
  pocos FPS, marcador ausente y dificultad para salir/cambiar de mesa.
- Se integra ScoreView estático con diseños DMD/alfanuméricos y recursos LF.
  Marcador embebido arriba a la derecha; no abre una segunda ventana ni B2S completo.
  El overlay se ajusta al render interno reducido para conservar su posición.
- B abre un menú propio morado con Continuar/Salir, cruceta y A. Consume las
  pulsaciones del menú y deja pasar las liberaciones para evitar botones atascados.
  Salir cierra la emulación normalmente y después solicita volver al NRO de GameClub;
  conserva NVRAM/configuración, sin guardar ni restaurar una partida.
- Perfil gráfico en tiempo de ejecución también para instalaciones existentes:
  853×480 internos con salida 1280×720, reflejos estáticos, sin AO/SSR/bloom/MSAA/FXAA.
  No modifica física, velocidad de PinMAME ni frecuencias de reloj. Reduce trabajo
  gráfico; no se afirma una ganancia de FPS hasta medirla en la consola.
- FPS visibles y registro cada diez segundos de tiempos de física, script,
  preparación, envío y presentación, además del nombre del renderizador OpenGL.
- Nueve regresiones nuevas de pausa, navegación, confirmación y salida: 27 de
  runtime, 167 comprobaciones totales. Tres vistas del mismo menú ImGui verificadas
  en escritorio, siete del lanzador y recorrido de carátulas con caché llena.
- Windows, móvil y TV compilados en 0.13.6+37. TV sin Visual Pinball; Raspberry sin
  cambios. Marcador, mejora de FPS y retorno efectivo requieren nueva prueba física.

## Versión anterior · 0.13.5

- Corrige el segundo arranque con caché de texturas: el cargador tomaba el mismo
  mutex dos veces al reutilizar una textura y además intentaba subirla a OpenGL
  desde un worker sin el contexto gráfico. Ahora los workers preparan/retienen
  datos CPU y una cola los sube después desde el propietario del contexto.
- Precarga de texturas con un worker en Switch para limitar memoria temporal.
- Corrige el mapa de controles y su documentación: + enviaba Escape, que en VPX
  standalone cierra la mesa. +/Y ahora envían Start (1) y B abre/retrocede en el
  menú (F12), con la acción Salir. La foto del propietario confirma mesa visible
  y reporta sonido al introducir monedas; todavía no confirma partida iniciada.
- Se conservan dos registros anteriores por mesa; un nuevo intento no borra
  inmediatamente el log previo. Se registran Start, moneda y menú.
- 18 regresiones nuevas de controles, cola gráfica y rotación de logs: 158
  comprobaciones totales. Windows, móvil y TV 0.13.5+36; motores anteriores
  conservados, TV sin VPX y Raspberry sin cambios. Nueva prueba física pendiente.

## Versión anterior · 0.13.4

- Corrige el siguiente fallo confirmado por South Park: `FBShader.glfx` pedía
  GLSL 4.50, pero el compilador gráfico de Switch admite hasta 4.30. El motor
  adapta la cabecera a 4.30 y el paquete ya distribuye los recursos con ese límite.
- La validación gráfica ahora exige GLSL 4.30 con glslc del NDK, además de compilar
  y enlazar los 83 programas mono en la GPU de escritorio. Se verifica también
  que ninguna fuente generada supere 4.30. La validación anterior en NVIDIA no
  detectó el requisito 4.50 porque su driver lo aceptaba con un contexto 4.3.
- 140 comprobaciones: 51 del cliente, 8 de hilos, 9 de formatos y 72 GLFX,
  incluyendo seis regresiones nuevas de adaptación/preservación de versiones.
- Se conservan las correcciones de navegación, CRLF y VSync. Windows, móvil y
  TV 0.13.4+35; TV sin VPX y Raspberry sin cambios. Nueva prueba física pendiente.

## Versión anterior · 0.13.3

- Corrige la lectura de los shaders GLFX en Horizon: los finales CRLF dejaban
  `TECHNIQUES\r` y otras secciones con nombres distintos, por lo que se compilaban
  cero programas. El parser compartido elimina CR/BOM, propaga errores de includes
  y detecta la ausencia de técnicas. El ZIP distribuye los shaders con finales LF.
- El modo de frame pacing de escritorio se adapta a VSync en Switch antes de
  crear el renderizador, evitando el aviso del dispositivo DWM/DXGI inexistente.
- 66 comprobaciones nuevas de GLFX: 10 archivos, 94 técnicas, secciones y funciones
  equivalentes con LF/CRLF/BOM, includes ausentes/incorrectos y recursión. Se suman
  a las 68 anteriores del cliente, hilos y formatos.
- Los 83 programas usados por el modo de una pantalla se han compilado y enlazado
  en OpenGL 4.3 de escritorio con los shaders analizados por el nuevo parser.
  Esto comprueba GLSL e interfaces, no el driver de Switch ni emulación real.
- El propietario confirma navegación fluida con 0.13.2. No se cambia esa ruta.
- Windows, móvil y TV 0.13.3+34, con sus motores anteriores y TV sin VPX. Raspberry
  sin cambios. La ejecución jugable de una mesa en Switch sigue pendiente de prueba.

## Versión anterior · 0.13.2

- Corrige `Invalid Output format: 373694468`: el motor acepta RGBA8888 y otros
  órdenes de canales válidos de SDL con OpenGL de escritorio en Switch. La
  0.13.1 ya supera el cierre de hilos, carga plugins/audio y crea la ventana,
  pero el registro de la consola termina en esa validación de formato.
- Navegación del lanzador: caché LRU de 32 carátulas, sin expulsar por orden de
  nombre. Lectura, descarga, decodificación y escalado en segundo plano; subidas
  a GPU en el hilo gráfico y cola limitada. Las carátulas ausentes/dañadas no se
  vuelven a buscar en cada frame. Se evita consultar motores en SD en cada dibujo.
- El lanzador usa PadState para los mandos en Switch sin inicializar además los
  gamepads de SDL. Guarda `launcher-performance.json` al salir o abrir un motor
  para comprobar renderer, frames y actividad de carátulas en la consola.
- 51 comprobaciones de cliente, 8 de hilos y 9 de formatos. Prueba adicional de
  40 carátulas, páginas repetidas y archivos ausentes/dañados, más siete vistas.
- Windows, móvil y TV 0.13.2+33; se conservan los motores anteriores y la exclusión
  de VPX en TV. Raspberry sin cambios. Nueva prueba física pendiente: no se
  certifica todavía una mesa jugable ni los FPS de la interfaz en Switch.

## Versión anterior · 0.13.1

- Corrige la incompatibilidad del grupo de hilos de VPX con Horizon: el SDK no
  implementa `pthread_detach`. Ahora el motor espera con `join` al terminar la
  carga de la mesa, sin una excepción al liberar esos hilos. También se elimina
  el `detach` del contador de sincronización del renderizador standalone.
- Libera el búfer temporal de las imágenes antiguas durante la carga y comprueba
  fallos de asignación/conversión. Registra excepciones del motor y su versión.
- El motor local no inicializa sockets innecesarios. La foto de la primera prueba
  mostraba un fatal posterior en `bsdsocket`; no se afirma todavía que esta medida
  resuelva ese segundo síntoma.
- 47 comprobaciones del lanzador y 8 regresiones de hilos con la rama Horizon,
  incluidos cierre, trabajo pendiente, excepciones, crecimiento y reducción.
- Primera prueba de Fish Tales: VPX sí inicia y carga recursos; no se certifica
  todavía imagen, audio o una mesa jugable. Nueva prueba física pendiente.
- Windows, móvil y TV compilados como 0.13.1+32; conservan sus motores anteriores
  y TV sigue excluyendo Visual Pinball. Raspberry sin cambios.

## Versión anterior · 0.13.0

- Port nativo experimental de Visual Pinball X y PinMAME para Nintendo Switch,
  con complementos PinMAME, B2S y FlexDMD estáticos. No usa Android ni RetroArch
  para abrir mesas VPX.
- GameClub muestra Visual Pinball, descarga sus paquetes, valida tamaños/CRC,
  extrae los recursos con rutas comprobadas y solicita abrir el motor desde Homebrew Menu.
- Controles Joy-Con: L/ZL y R/ZR flippers, A lanzador, X/− moneda, Y inicio,
  B/+ menú. Acción **Salir**, partida nueva y NVRAM/configuración por mesa.
- ZIP de SD con lanzador, NRO del motor, scripts, fuentes, imágenes y shaders.
  Sin mesas ni ROMs. Guía de instalación y registros: `SWITCH_PINBALL.md`.
- 47 comprobaciones nativas, siete vistas del lanzador y 47 pruebas Flutter.
- Tras el bloqueo comunicado en la primera prueba física: escritura con búfer,
  progreso de extracción, cancelación, reintento con descarga conservada y
  registro `pinball-prepare.log`. La ejecución de mesas sigue en prueba.
  **Pendiente de prueba física:** arranque, vídeo, audio, mandos y rendimiento
  real de cada mesa. La compilación no equivale a esa prueba.
- Windows, móvil y TV se entregan como 0.13.0+31. PC y móvil conservan VPX;
  TV mantiene su exclusión y conserva los pinballs MAME.

## Versión anterior · 0.12.0

- Primer cliente nativo homebrew para Nintendo Switch, distribuido como NRO ARM64.
  Biblioteca retro morada, carátulas, búsqueda, favoritos compartidos, filtros por
  consola y ajustes de servidor/token con el teclado de Switch.
- Abre núcleos de RetroArch para Switch instalados por el usuario. Detecta los
  disponibles y prepara los juegos en la SD; MAME resuelve sus dependencias con
  los planes de la Raspberry. No incluye emuladores, BIOS ni ROMs.
- Caché aislada por servidor y revisión del juego, descargas temporales comprobadas
  por tamaño y rutas validadas. MAME/NES/Atari usan sesiones nuevas y otras consolas
  conservan batería local; no se modifica el archivo de configuración de RetroArch.
- Control por cruceta/stick, A/B/X/Y, L/R, ZL/ZR, pantalla táctil y salida con +.
- Compilación y estructura NRO comprobadas; 33 comprobaciones nativas y vistas del
  mismo código SDL2 verificadas en escritorio. Falta probar arranque, controles y
  lanzamiento efectivo de los núcleos en una Switch física. Guía: `SWITCH.md`.
- Windows, móvil y TV se entregan también como 0.12.0+30. TV sigue excluyendo VPX;
  PC y móvil lo conservan y se mantiene la política de guardados por sistema.

## Versión anterior · 0.11.0

- Nueva biblioteca retro: predominio del morado, acentos menta/rosa/amarillo,
  tipografía Press Start 2P, dibujos pixel art y marcos negros escalonados.
- Menú lateral en ventanas amplias de PC y navegación inferior adaptada a
  móvil y TV; disposición compacta para pantallas horizontales o de poca altura.
- Carátulas y fichas renovadas, bandas de color por sistema, estrellas de
  favoritos y foco de mando visible en menta. Las fichas muestran su portada.
- Búsqueda, filtros por consola, favoritos, subida de juegos y ajustes se
  mantienen; mensajes distintos para búsquedas vacías y favoritos sin juegos.
- Corregidos recortes con teclado, ventanas pequeñas y selectores largos al
  conectar un mando al móvil. Se conserva la política de guardados de 0.10.4.
- PC/móvil conservan Visual Pinball; TV sigue ocultándolo y excluyendo su motor.

## Versión anterior · 0.10.4

- MAME, NES, Atari 2600 y pinball muestran **Salir** y comienzan una partida nueva
  en cada apertura. No se restauran las partidas de sesiones anteriores.
- Los motores nativos MAME/NES/Atari usan una carpeta temporal por sesión que se
  elimina al cerrar. Se desactiva la carga y escritura automática de SRAM.
- MAME web no restaura NVRAM/estados ni exporta guardados. El modo libretro web
  usa memoria temporal sin montar la base de partidas del navegador.
- Nintendo DS y las demás consolas conservan batería/SRAM y guardado al salir.
- Pinball conserva su NVRAM y configuración de máquina para evitar repetir la
  inicialización de fábrica, sin guardar una instantánea de la partida.

## Versión anterior · 0.10.3

- Corregidas las carátulas de Visual Pinball/PinMAME: se reconocen los folletos
  frontales de las máquinas y los nombres de imagen `r2_` de LaunchBox.
- Las capturas de pinball se descargan de LaunchBox, separadas de las carátulas,
  con fuente identificada y sin duplicar imágenes idénticas.
- Índice LaunchBox v3: migración automática del índice anterior e invalidación
  de consultas vacías de capturas de pinball. Se conservan las imágenes propias.
- La búsqueda elimina sufijos de autor y versión VPW/g5k/VPX de las mesas.
- Corrección desplegada en la Raspberry: comprobadas carátulas y capturas de
  las 14 mesas VPX presentes. También funciona con las apps anteriores.

## Versión anterior · 0.10.2

- VPX móvil: cámara ajustada a la geometría completa, sin el zoom ni la rotación
  heredados de una configuración de mueble de la mesa.
- Superficie de vídeo proporcionada al girar el móvil, sin estirar la mesa ni
  reiniciar la partida.
- Vista de mueble para evitar el DMD de escritorio duplicado; el marcador
  adicional ScoreView puede desactivarse desde el menú de GameClub.
- Balance inicial de audio: mecánica al 35% y música/electrónica al 100%.
  PinMAME utiliza el canal backglass, separado de la mecánica.
- Nuevo menú **Imagen y sonido**: volumen mecánico, volumen de música/ROM,
  tamaño de mesa (70–100%) y marcador adicional, guardados por mesa.
  Aplicar los cambios reinicia la partida y conserva la NVRAM.
- Los ajustes se aplican también a las instalaciones existentes antes de cargar
  la mesa. Menús desplazables en pantallas horizontales.

## Versión anterior · 0.10.1

- La variante TV oculta Visual Pinball en biblioteca, favoritos y selectores de
  subida, incluso al mostrar sistemas vacíos.
- El APK TV deja de incluir las bibliotecas y recursos de VPX. Conserva los
  pinballs MAME y sus otros motores compatibles.
- PC y móvil mantienen Visual Pinball. Conectar un mando al móvil no lo oculta.
- Se conservan las mesas y guardados del servidor para PC y móvil.

## Versión anterior · 0.10.0

- **VPX y PinMAME integrados en el APK Android**: reproducción desde GameClub,
  sin instalar la aplicación oficial externa ni confirmar importaciones.
- Actividad de emulación en proceso separado, conservando mesas, configuración
  y NVRAM por servidor y juego.
- Botones táctiles para monedas, partida, lanzador y flippers; disposición
  vertical/horizontal que reserva espacio para los controles.
- Mando y menú Start + Select / Atrás: continuar, reiniciar y guardar/salir.
- Bibliotecas y recursos originales fijados por SHA-256, incluidos en móvil y TV.
- VPX requiere Android 13+ ARM64 y OpenGL ES 3.2 o Vulkan. Los otros motores
  conservan el soporte anterior de GameClub.
- Comprobación real del motor ARM64 integrado en un emulador con traducción:
  Vulkan, vídeo 3D, flipper táctil, menú y vuelta a la biblioteca.

## Versión anterior · 0.9.1

- Windows: VPX recibe el foco al arrancar y al continuar, evitando la mesa
  aparentemente congelada.
- Mando SDL para monedas, partida, lanzador, flippers y golpes de mesa.
- Menú **Start + Select / Guide / Esc**, con controles visibles, continuar,
  reiniciar y guardar/salir.
- Liberación de botones al pausar, desconectar o cambiar de aplicación.
- Monedas secuenciadas y espera de créditos antes de iniciar con Start.
- Preparación inicial de Attack from Mars sin borrar NVRAM ni originales.
- Backend compatible con el servidor 0.9.0 ya desplegado.

## Versión anterior · 0.9.0

- Nuevo sistema **Visual Pinball · PinMAME**: un ZIP/VPXZ por mesa con ROMs,
  panel B2S opcional, música y script standalone.
- Windows prepara y verifica el motor oficial portátil VPX BGFX x64, ejecuta la
  mesa a pantalla completa y conserva configuración/NVRAM por juego y servidor.
- Android 13+ ARM64 prepara el paquete para importarlo en Visual Pinball oficial;
  informa de dispositivos incompatibles antes de descargarlo.
- Filtro de pinballs MAME por familias conocidas, manteniendo el motor arcade.
- Catálogo LaunchBox de pinball y reconstrucción de índices de carátulas.
- Guía: [PINBALL.md](https://github.com/Pablocg04/GameClub/blob/master/PINBALL.md).

Verificación: 87 pruebas del servidor, 32 del cliente y análisis Flutter limpio;
Attack from Mars con ROM hija/padre en Windows, partida, flippers, salida y NVRAM.
VPX Android ARM64 físico sigue pendiente de comprobar.

## Correcciones anteriores · 0.8.1

- Corregido el lápiz táctil de Nintendo DS en Android, incluida la liberación al
  levantar/cancelar el dedo o abrir el menú.
- La caché detecta ROMs reemplazadas aunque tengan el mismo tamaño y separa las
  descargas generales por servidor.
- Corregido el desbordamiento de biblioteca/diálogos en ventanas bajas con teclado.
- Recuperación automática de índices de carátulas incompletos y ZIPs dañados.
- Mayor plazo para preparar por primera vez los catálogos de búsqueda individual.
- Se mantienen NES y Atari 2600 nativas, arcade nativo y la búsqueda de carátulas
  Libretro → LaunchBox → GameTDB, con subida manual disponible.

Verificación: 75 pruebas del servidor, 29 del cliente, dos de C++ e integración
real en Windows y en emuladores Android móvil/Google TV. Informe y límites de la
revisión: [VERIFICATION.md](https://github.com/Pablocg04/GameClub/blob/master/VERIFICATION.md).

## Descargas

- **Windows:** extraer el ZIP completo y abrir `GameClub/gameclub.exe` manteniendo
  las DLL y la carpeta `data/` junto al ejecutable.
- **Móvil/tablet:** instalar `GameClub-Android.apk`.
- **Android TV/Google TV:** instalar `GameClub-AndroidTV.apk`.

Las apps no incluyen juegos, BIOS ni guardados personales. Los APK móvil y TV son
variantes para dispositivos diferentes y actualizan la instalación anterior.
