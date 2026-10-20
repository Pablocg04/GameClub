# GameClub

Código: <https://github.com/Pablocg04/GameClub>. Descargas:
<https://github.com/Pablocg04/GameClub/releases>.

Biblioteca de videojuegos alojada en una Raspberry Pi 5, con cliente para **Windows y Android**.
La Raspberry organiza y entrega los archivos; los emuladores se ejecutan en el dispositivo de juego.

## Android y Android TV · 0.10.0

- **Móvil/tablet:** `dist/android-mobile-0.10.0/GameClub-Android.apk`.
  Controles clásicos grandes y juego vertical u horizontal. [ANDROID_MOBILE.md](ANDROID_MOBILE.md).
- **Android TV / Google TV:** `dist/android-tv-0.10.0/GameClub-AndroidTV.apk`.
  Launcher de TV, orientación horizontal y navegación por mando. [ANDROID_TV.md](ANDROID_TV.md).

Son dos variantes de la misma base y conservan los datos al actualizar el paquete
anterior. Los sistemas integrados arrancan directamente. **Start + Select** abre
el menú durante el juego.

**LB/RB o L1/R1** cambia de pestaña y **Select** abre búsqueda y teclado.

**0.6.0 sustituye la ruta arcade web por MAME nativo** en móvil, TV y Windows.
Los juegos arrancan directamente a pantalla completa, sin barra superior. El móvil
recibe mandos Bluetooth/USB, adapta la navegación al conectar un mando y los menús
conservan su foco. Los controles táctiles arcade tienen cruceta, A/B/X/Y, L/R y
Select/Start. Consulta [MAME_NATIVE.md](MAME_NATIVE.md).

El paquete Windows está en `dist/windows-0.10.0/` e incluye el host nativo.
**0.7.0 añade NES y Atari 2600 nativas**, con Nestopia UE y Stella incluidos en
las tres apps. Consulta [NATIVE_CONSOLES.md](NATIVE_CONSOLES.md).

**0.8.0 busca carátulas en Libretro → LaunchBox → GameTDB**, pasando a la siguiente
fuente si no encuentra una imagen compatible. Se conserva la subida manual.
Todas las fuentes funcionan sin cuenta ni claves.

**0.8.1 corrige el lápiz NDS móvil, la invalidación y separación de cachés, las
ventanas con teclado y la recuperación de catálogos incompletos.** Consulta el
informe reproducible [VERIFICATION.md](VERIFICATION.md).

**0.9.0 añade Visual Pinball · PinMAME**, subida de un paquete por mesa y motor
portátil verificado en Windows. Android 13+ ARM64 importa la mesa en VPX oficial.
El icono de bola filtra los pinballs de vídeo de MAME. Consulta [PINBALL.md](PINBALL.md).

**0.9.1 corrige el foco de VPX en Windows e integra mando, ayuda de controles y
menú Start + Select / Esc**, con continuar, reiniciar y guardar/salir.

**0.10.0 integra VPX y PinMAME en el APK Android**, con botones táctiles,
mando, menú y guardados por juego. No necesita instalar Visual Pinball aparte.
Requiere Android 13+ ARM64 y gráficos OpenGL ES 3.2 o Vulkan para pinball.

## Versión · 0.10.0

Implementado:

- Catálogo de 19 sistemas, incluidos NES, Atari 2600 y Visual Pinball, mostrando por defecto solo sistemas con juegos.
- Interfaz adaptable, carátulas, búsqueda, favoritos y ajustes de conexión.
- Galería de capturas en la ficha: descarga automática de Libretro, ampliación
  con zoom y subida múltiple de imágenes propias, guardadas en la Raspberry.
- Escaneo al arrancar el servidor y botón para volver a escanear.
- Subida de juegos desde la app: propone consola si la extensión es inequívoca,
  pide confirmación y coloca el archivo en `roms/<consola>/`. Si seleccionas varias
  ROMs, eliges la consola una sola vez para todo el lote, con progreso y resumen.
- Alta manual de consolas, sin crear sistemas adicionales en la biblioteca inicial.
- Detección de tracks CUE y listas M3U para evitar duplicarlos como juegos.
- Carátulas manuales y búsqueda pública de Libretro con selección del resultado.
- Libretro Thumbnails sin claves para búsqueda individual y scrape masivo,
  con catálogo de nombres MAME. Consulta [THUMBNAILS.md](THUMBNAILS.md).
- Consultas serializadas y caché de catálogos públicos, sin cuenta ni claves.
- Acceso API editable, comprobación de conexión y scrape de toda la biblioteca
  en segundo plano con progreso, cancelación y continuación de pendientes.
- Descarga local por streaming con progreso; reutiliza el archivo si su tamaño coincide.
- Windows: selección de ejecutable por consola y apertura pasando el archivo como argumento.
- Arcade integrado con MAME 2003-Plus, MAME 2003 y FinalBurn Neo: selección
  automática, alternativas ante errores y memoria del núcleo por juego.
  Incluye caché y auditoría de compatibilidad. Consulta [MAME.md](MAME.md).
- Identificación de revisiones históricas por CRC/tamaño cuando cambia el código
  entre romsets. Super Basketball H se reconoce como `sbasketh` en FBNeo sin
  modificar el ZIP original. Los juegos no incluidos muestran un motivo específico.
- MAME completo nativo para ampliar la cobertura arcade, con dependencias del
  catálogo histórico 0.130u3. Barline, Casino Fever 6.1 y Royal Casino ya se abren
  por la ruta nativa. Consulta [MAME_NATIVE.md](MAME_NATIVE.md).
- Android: apertura genérica del archivo mediante una aplicación compatible instalada.
- Servidor FastAPI/SQLite y configuración Docker compatible con ARM64.
- Reproductor dentro de GameClub para MAME, NDS, GB, GBC, GBA, SNES y N64,
  con controles, menú y guardado local. Consulta [PLAYER.md](PLAYER.md).
- Perfiles rápido/equilibrado de NDS y medición de velocidad en el reproductor.

### Alcance del lanzamiento

La apertura genérica **no garantiza el lanzamiento en todos los emuladores**. Algunos requieren
argumentos, actividades Android o importación específicos. Estos adaptadores serán la siguiente fase.
Los controles táctiles y los mandos durante el juego los gestiona el emulador externo.

NDS y los sistemas clásicos de [PLAYER.md](PLAYER.md) se reproducen dentro de
la app, sin instalación de emuladores independientes. Arcade utiliza varios núcleos
y los sistemas más exigentes utilizan sus emuladores externos.

Para arcade se preparan los ZIP y los discos CHD como se explica en
[MAME.md](MAME.md). Para los otros sistemas, la apertura de `.cue`, `.m3u`,
archivos de instalación y comprimidos sigue pendiente: la descarga genérica entrega
solo el archivo principal, sin preparar tracks, discos, instalación ni extracción. Wii U con carpetas
`code/content/meta` y juegos de Vita instalados requieren tratamiento específico.

Pendiente: más adaptadores, gestión de BIOS/firmware e instaladores desde la app,
ajustes globales de mandos, idioma configurable, sincronización de partidas,
caché con límites y verificación por hash. El idioma actual de la interfaz es español.

## Carpetas confirmadas

| Carpeta | Sistema |
|---|---|
| `gb` | Game Boy |
| `gba` | Game Boy Advance |
| `gbc` | Game Boy Color |
| `gc` | GameCube |
| `mame` | Arcade · MAME |
| `n3ds` | Nintendo 3DS |
| `n64` | Nintendo 64 |
| `nds` | Nintendo DS |
| `ps2` | PlayStation 2 |
| `psp` | PSP |
| `psvita` | PlayStation Vita |
| `psx` | PlayStation |
| `snes` | Super Nintendo |
| `switch` | Nintendo Switch |
| `wii` | Nintendo Wii |
| `wiiu` | Nintendo Wii U |
| `vpinball` | Visual Pinball · PinMAME |

Dreamcast, Mega Drive, Saturn, PS3 y OpenBOR no se crean automáticamente.
`Pack Emuladores/` y `roms/` permanecen fuera de Git; sus archivos son biblioteca local.

## Servidor en la Raspberry

El servidor ya está desplegado en **`http://192.168.0.47:8001`**, con el contenedor
`gameclub` y las carpetas en `/home/pablo/proyectos/GameClub`.
Consulta [DEPLOYMENT.md](DEPLOYMENT.md) para añadir ROMs, controlar el contenedor
desde el móvil y gestionar el servicio por SSH.

Con Docker y Docker Compose ya instalados, copia este proyecto a una carpeta de la Raspberry.
Desde esa carpeta:

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f gameclub
```

La app usa por defecto **`http://192.168.0.47:8001`**. Si el puerto está ocupado por otro
proyecto, cambia `GAMECLUB_PORT` en `.env` y la dirección en Ajustes.

El servicio mantiene su propia red de Compose y sus volúmenes. Se puede añadir el bloque
`gameclub` a un Compose existente adaptando la ruta `build` y los montajes.

Volúmenes persistentes:

```text
roms/       Juegos por consola
data/       Base de datos SQLite
media/      Carátulas descargadas o subidas
```

Si las ROMs están en otra ubicación de la Raspberry, cambia el origen del montaje:

```yaml
volumes:
  - /ruta/real/roms:/library/roms
  - ./data:/library/data
  - ./media:/library/media
```

Introduce tus juegos en esas carpetas y pulsa **Escanear biblioteca**. Las carpetas vacías
no se muestran por defecto. Puedes activarlas en Ajustes para consultar los sistemas registrados.

Estado del servidor: `http://192.168.0.47:8001/health`.
Documentación de la API: `http://192.168.0.47:8001/docs`.
Si configuras `GAMECLUB_API_TOKEN`, introduce el mismo valor en los ajustes del cliente.
Para usar la API directamente, envía `Authorization: Bearer <token>`.

## Carátulas

### Libretro · integrado sin claves

El modo predeterminado consulta **Libretro → LaunchBox → GameTDB**. Puedes buscar
carátulas y procesar la biblioteca sin registrarte ni configurar una API key.
Consulta [THUMBNAILS.md](THUMBNAILS.md). Las carátulas y descripciones anteriores
se conservan. Los nombres compactos de NES y las etiquetas de Atari se normalizan
antes de buscar. ScreenScraper se retiró en 0.7.1.

#### Scrapear todos los juegos

En los mismos ajustes, pulsa **Scrapear todos los juegos**. El trabajo se ejecuta
en la Raspberry y continúa aunque cierres la app. Por defecto omite juegos que ya
tengan carátula; puedes marcar **Actualizar también juegos que ya tengan carátula**.

La app consulta el progreso cada tres segundos y muestra el juego actual, los
actualizados, los omitidos y los errores. **Resultados recientes** muestra las
últimas 50 entradas. Solo hay un trabajo activo para toda la biblioteca.

Los resultados ambiguos o sin coincidencia fiable se omiten para que puedas
resolverlos desde la ficha individual. Las consultas se realizan en serie y
respetan un intervalo entre peticiones. Ante un error general de conexión, el lote
se pausa sin intentar los demás juegos.

**Cancelar scrape** termina el trabajo al completar el juego en curso.
**Continuar pendientes** permite seguir después de cancelar, de una pausa o de un
reinicio del servidor. La cola y el progreso quedan guardados en la Raspberry.

### Otras opciones

- **Imagen manual**: ya disponible en la ficha del juego, sin proveedor externo.

## Preparar el cliente Windows/Android

Herramientas:

1. [Flutter estable](https://docs.flutter.dev/install), con `flutter/bin` en el PATH.
2. Para Windows: Visual Studio con la carga **Desarrollo para el escritorio con C++**.
3. Para Android: Android Studio, SDK y **Android SDK Command-line Tools**.
4. Si Flutter solicita enlaces simbólicos, activa **Modo de desarrollador** en Windows.

Comprueba el entorno:

```powershell
flutter doctor
flutter doctor --android-licenses
```

Desde la carpeta `client/`:

```powershell
.\bootstrap.ps1
flutter analyze
flutter test
flutter run -d windows
```

Para generar distribuciones:

```powershell
flutter build windows --release
flutter build apk --release --flavor mobile
flutter build apk --release --flavor tv
```

Salidas:

- Windows: distribuye la carpeta completa `client/build/windows/x64/runner/Release/`.
- Android móvil: `client/build/app/outputs/flutter-apk/app-mobile-release.apk`.
- Android TV: `client/build/app/outputs/flutter-apk/app-tv-release.apk`.

La actualización Windows **0.6.0** está disponible como paquete independiente en
`dist/windows-0.6.0/gameclub.exe`, compilado por separado del ejecutable anterior.
Conserva toda la carpeta de ese paquete.

### Compilaciones disponibles en este equipo

Se han generado correctamente ambas versiones `release`:

- **Windows:** abre `dist/windows-0.6.0/gameclub.exe`.
  Conserva `flutter_windows.dll` y la carpeta `data/` junto al ejecutable.
  Se comprobó su arranque y la apertura de la ventana.
- **Android móvil:** instala `dist/android-mobile-0.6.1/GameClub-Android.apk`.
- **Android TV:** instala `dist/android-tv-0.6.1/GameClub-AndroidTV.apk`.
  Ambos APK se han compilado y probado en emuladores dedicados de móvil y Google TV.

Las compilaciones se guardan en `build/` y no se incluyen en Git.
En ambas aplicaciones, el servidor inicial es `http://192.168.0.47:8001`;
para consultar juegos debe estar arrancado el servicio de la Raspberry.

Entorno utilizado: Flutter 3.47.7, Visual Studio Community 2026 18.10.3 y
el SDK Android instalado con Android Studio. Gradle preparó el NDK, la plataforma
Android y CMake necesarios usando las licencias ya aceptadas en este SDK.

Esta fase usa la firma de desarrollo generada por Flutter para Android. Antes de distribuir
actualizaciones estables se configurará una clave de firma propia.

Para sistemas externos en Windows, selecciona su `.exe` en **Ajustes → Emuladores**.
Para sistemas externos en Android, instala el emulador correspondiente. Si no admite abrir el archivo desde otra app,
puedes descargar el juego y abrirlo desde el propio emulador hasta incorporar su adaptador.

## Desarrollo del servidor en Windows

Desde la raíz, con Python instalado:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server/requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000
```

Para probar cliente y servidor en el mismo PC, usa `http://127.0.0.1:8000` en Ajustes.
El servidor de desarrollo toma las variables del proceso; Uvicorn no carga `.env`
automáticamente con este comando. Docker Compose sí utiliza el archivo `.env`.

Pruebas, desde `server/`:

```powershell
..\.venv\Scripts\python.exe -m pytest tests -q
```

## Verificación realizada

- API: 50 pruebas pasando, incluyendo catálogo, scrape, capturas, identificación arcade, MAME web y caché
  de motores integrados con validación de rutas y autenticación.
- Cliente: 14 pruebas unitarias/de interfaz y pruebas de integración reales del
  reproductor en Windows y Android. Consulta [PLAYER.md](PLAYER.md).
- Flutter usado para verificar: 3.47.7 / Dart 3.13.5.
- Compilaciones nativas Windows y Android en modo `release`: correctas.
- Arranque de la aplicación Windows: comprobado.
- Arcade automático: `mslug` con FBNeo y su BIOS; `sf2` con MAME 2003-Plus después
  de un fallo de arranque simulado; rechazo de la pantalla FBNeo Error al faltar
  una BIOS. `kinst` sigue sin un núcleo compatible entre los disponibles.
- Docker en la Raspberry ARM64: imagen construida y contenedor saludable.
- API accesible en la red local; arranque/parada del contenedor y configuración
  de inicio automático de Docker comprobados.
- Reproductor real: vídeo y controles de NDS, GB, GBC, GBA y SNES comprobados en
  Windows y un emulador Android, incluyendo lápiz NDS y SRAM persistente de GB.
- Pendientes: pruebas en móvil físico, N64 con una ROM real, consulta real a
  ScreenScraper y los demás emuladores externos del pack.

## Próximo hito

Ampliar las comprobaciones del romset arcade, mandos físicos y rendimiento en el móvil,
y continuar con los adaptadores de otros sistemas.
