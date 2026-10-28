# GameClub 0.10.3

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
