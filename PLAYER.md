# Reproductor integrado · GameClub 0.6.0

Todos los sistemas integrados arrancan directamente a pantalla completa, sin
barra superior. El mando Android funciona en móvil y TV; el menú tiene foco
explícito para cruceta y A/B. Arcade utiliza el [reproductor nativo](MAME_NATIVE.md).

GameClub reproduce estos sistemas dentro de su propia ventana o pantalla, sin
instalar una aplicación de emulación independiente:

Desde el cliente Android 0.4.0 también hay modo Android TV, con autoarranque,
mandos nativos y menú accesible sin tacto. Consulta [ANDROID_TV.md](ANDROID_TV.md).

| Sistema | Motor |
|---|---|
| Nintendo DS | DeSmuME |
| Game Boy / Game Boy Color | Gambatte |
| Game Boy Advance | mGBA |
| Super Nintendo | Snes9x |
| Nintendo 64 | Mupen64Plus-Next |
| Arcade / MAME | MAME 2003-Plus, MAME 2003, FinalBurn Neo y MAME completo nativos |

Los motores de consola se ejecutan en el dispositivo mediante **EmulatorJS 4.2.3 / WebAssembly**.
Windows usa WebView2 y Android la vista web del sistema. La Raspberry sirve los
archivos y conserva una caché de motores; no ejecuta la emulación.

Para arcade se prueban los candidatos compatibles, se detectan errores de arranque
y se recuerda el núcleo que funciona. Consulta [MAME.md](MAME.md). La app permite
reproducción de audio sin una nueva interacción al cambiar automáticamente de núcleo.

## Jugar

1. Añade una ROM a la consola correspondiente desde GameClub.
2. Abre su ficha y pulsa **Jugar en GameClub**.
3. La app prepara la ROM y abre el reproductor.
4. Pulsa **Iniciar juego** dentro del reproductor.

En la primera carga, la Raspberry necesita Internet para descargar los recursos
del motor. Se guardan tanto en su volumen persistente como en la caché de la app.
Las siguientes cargas reutilizan esos recursos, sin instaladores ni APK de plugins.

NDS utiliza `.nds` o sus comprimidos. Los títulos DSi `.dsi` necesitan otra
integración. Los ZIP/7z de los sistemas clásicos los descomprime el reproductor.

## Controles

- Android: botones táctiles, cruceta y botones propios de cada consola.
- NDS: las dos pantallas y entrada de lápiz en la pantalla inferior; ratón en PC
  y tacto en Android. El diseño de pantallas puede ajustarse desde el menú del motor.
- PC: teclado y mandos que el sistema exponga mediante la API Gamepad.
- Android: mandos que Android/WebView expongan mediante esa misma API.
- Usa **Ajustes de Control** para mapear botones y seleccionar jugadores/mandos.
- El menú inferior incluye pausa, volumen, opciones del motor y estados de guardado.
  Aparece al iniciar y se oculta después de unos segundos; puedes volver a abrirlo.

## Rendimiento de Nintendo DS

En **Ajustes → Emuladores → Rendimiento de Nintendo DS** puedes elegir:

- **Rápido**: resolución nativa 256×192, salto de un fotograma, temporización
  avanzada desactivada, menos posprocesado y dos hilos si la vista web permite
  SharedArrayBuffer. Carga en memoria ROMs de hasta 128 MiB.
- **Equilibrado**: sin salto de fotogramas y con temporización precisa.

El cambio se aplica al cerrar y volver a abrir el juego. Android utiliza Rápido
por defecto en esta versión. Los controles ajustados en el reproductor se guardan
por perfil; la batería/SRAM del juego se conserva al cambiar de perfil.

Durante NDS se muestra una medición de fotogramas y velocidad aproximada. El
multihilo se indica cuando realmente está disponible, con alternativa a un solo
hilo si la vista web no lo admite.

Este motor WebAssembly usa un intérprete de CPU, sin JIT. Un móvil potente no
elimina ese coste: algunos juegos 3D pueden seguir sin alcanzar velocidad completa.
Para un salto mayor de rendimiento sería necesaria una integración de motor nativo.

## Partidas

Las partidas se guardan **localmente en cada dispositivo**. El reproductor
actualiza la batería/SRAM periódicamente y la confirma antes de cerrar.
Los estados de guardado del menú se conservan en el almacenamiento del reproductor.
Esta fase no sincroniza partidas entre PC y móvil.

Usa **Volver a la biblioteca** o **Volver a GameClub** para cerrar. La app espera
la confirmación de escritura antes de desmontar el motor y volver a la biblioteca.

Rutas bajo el directorio privado de soporte de la app:

```text
player/emulatorjs-4.2.3/                 Recursos de motores
player/saves/<servidor>/<juego>/battery.zip  Batería/SRAM con su ruta virtual original
player-webview/                         Perfil WebView2 en Windows
```

La descarga de ROMs utiliza `Documentos/GameClub/games/<juego>/` en Windows y
el directorio de documentos de la app en Android.

## Comprobaciones reales

Se han ejecutado programas de prueba propios de NDS, GB, GBC, GBA y SNES en:

- La vista WebView2 real de Windows.
- Android API 36.1, en un dispositivo virtual limpio.

Las comprobaciones verifican avance de fotogramas, imagen generada por cada
consola, respuesta al teclado en PC y a los botones táctiles en Android.
También comprueban la entrada de lápiz NDS y la conservación de SRAM de Game Boy
al cerrar y volver a abrir.

Nintendo 64 tiene su motor y perfil integrados, pendiente de comprobar con una ROM
real. Los mandos Bluetooth/USB deben probarse también en los dispositivos físicos.

## Desarrollo

El servidor expone `GET /api/player` y `GET /api/player/assets/<recurso>`.
Los recursos se descargan desde la versión fijada del CDN de EmulatorJS y se
cachean en `data/player/emulatorjs-4.2.3/`. Las rutas se validan y mantienen la
autenticación habitual de GameClub.

La app usa un servidor privado en `127.0.0.1:43871` para proporcionar al motor
un origen estable, acceso a la ROM preparada y almacenamiento local. No requiere
abrir ese puerto en la Raspberry ni en el router.

La integración de guardado tiene un adaptador específico para la versión 4.2.3:
exporta la batería a un ZIP nativo, la repone después de montar IDBFS y espera la
sincronización de salida. Debe verificarse al actualizar EmulatorJS.

Pruebas reproducibles:

```powershell
# Desde la raíz, deja abierto un servidor de datos de prueba independiente:
.\.venv\Scripts\python.exe tools/player_fixture.py "<carpeta temporal>" --llvm "<bin de LLVM del NDK>"

# Desde client:
flutter test integration_test/player_test.dart -d windows
flutter test integration_test/player_test.dart -d <emulador> --dart-define=PLAYER_TEST_SERVER=http://10.0.2.2:8687
```

El generador construye programas propios. Las pruebas no añaden juegos a la
Raspberry ni usan la biblioteca real. La configuración persistente de compilación
Windows se aplica desde `bootstrap.ps1` y `platform-config/windows-compat.cmake`.
