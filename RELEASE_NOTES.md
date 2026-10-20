# GameClub 0.10.0

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
