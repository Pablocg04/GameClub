# Revisión funcional · GameClub 0.9.0

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
