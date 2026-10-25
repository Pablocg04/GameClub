# GameClub móvil · 0.10.1

Instala `dist/android-mobile-0.10.1/GameClub-Android.apk` en el teléfono o la tablet.
La variante de televisión está en `dist/android-tv-0.10.1/GameClub-AndroidTV.apk`.
Ambas se compilan desde una base compartida; sus menús, orientación y lanzador
se seleccionan durante la compilación.

NES y Atari 2600 se ejecutan nativamente con Nestopia UE y Stella, incluidos en
el APK. Comparten el menú, los controles táctiles y la orientación del reproductor
nativo. Los `.sta` de Atari son estados externos y no aparecen como juegos.
Detalles: [NATIVE_CONSOLES.md](NATIVE_CONSOLES.md).

## Controles grandes

El reproductor MAME recupera el estilo de mando clásico: cruceta gris circular,
botones A/B/X/Y grandes y L/R, Select, Start y menú. El tamaño se calcula en dp,
adaptado a la densidad y al espacio disponible, en lugar de limitarse a 84 píxeles
físicos. En el teléfono de pruebas los botones tienen 72 dp de diámetro.

En **Ajustes → Pantalla y controles del móvil → Tamaño de los controles arcade**
puedes ajustar el tamaño entre el 80% y el 135%; el diseño respeta los límites de
la pantalla. Se aplica al abrir de nuevo el juego.

## Jugar en vertical u horizontal

En **Ajustes → Pantalla y controles del móvil → Orientación del juego**:

- **Automática (girar el móvil):** sigue la rotación y el bloqueo de giro de Android.
- **Vertical:** mantiene el juego en vertical.
- **Horizontal:** mantiene el juego en horizontal.

En MAME vertical, la imagen ocupa la zona superior y los controles se colocan
debajo, sin tapar el juego. En horizontal, el mando se distribuye en los laterales.
El giro automático reorganiza la pantalla sin reiniciar la partida. Se conservan
las proporciones originales de la imagen.

La orientación también se aplica a las consolas integradas. Los controles táctiles
de esas consolas siguen siendo los de su motor.

## Actualización

Los dos APK conservan `com.gameclub.gameclub`, para actualizar la instalación
anterior y preservar conexión, caché y guardados. Son alternativas por dispositivo:
instala el APK móvil en el teléfono y el de TV en el televisor.
La versión es **0.10.1**, código **25**, Android 7/API 24+, ARM32/ARM64/x86_64.
Visual Pinball requiere Android 13+ ARM64 y OpenGL ES 3.2 o Vulkan; el motor va
incluido en GameClub y se abre con **Jugar pinball**, sin otra aplicación.
Incluye flippers táctiles, moneda, partida, lanzador y menú. Start + Select / Atrás
abre continuar, reiniciar y guardar/salir. Los pinballs MAME mantienen su motor.
Requisitos y guía: [PINBALL.md](PINBALL.md).
Incluye la corrección del lápiz NDS y las cachés. Revisión: [VERIFICATION.md](VERIFICATION.md).
Carátulas: Libretro → LaunchBox → GameTDB y subida manual, sin cuenta ni claves. Consulta
[THUMBNAILS.md](THUMBNAILS.md).

## Verificación

- 21 pruebas Flutter y 30 combinaciones geométricas de tamaño, densidad y escala.
- Teléfono Android emulado 1080×2400, densidad 420: partida vertical con vídeo,
  botones táctiles leídos por el motor, menú y segunda apertura.
- Cambio real de vertical a horizontal durante la partida, comprobando que el
  dibujo de los botones coincide con sus áreas táctiles.
- La variante TV mantiene orientación horizontal, launcher Leanback y mandos.

Las pruebas usan un servidor local aislado con una ROM propia y motores ya
cacheados, porque la Raspberry no estaba disponible durante esta verificación.
