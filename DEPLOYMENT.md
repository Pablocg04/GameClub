# Despliegue de GameClub en la Raspberry

## Ubicación y acceso

- Raspberry: `192.168.0.47`.
- Usuario SSH: `pablo`.
- Proyecto: `/home/pablo/proyectos/GameClub`.
- Contenedor Docker: `gameclub`.
- Proyecto Compose: `gameclub`.
- API: <http://192.168.0.47:8001>.
- Estado: <http://192.168.0.47:8001/health>.
- Documentación interactiva: <http://192.168.0.47:8001/docs>.

El puerto `8000` ya lo utiliza Zen0. GameClub publica el puerto `8001` de la
Raspberry hacia el puerto `8000` interno de su contenedor.

## Carpetas persistentes

```text
/home/pablo/proyectos/GameClub/
├── compose.yaml
├── .env
├── server/
├── roms/
│   ├── gb/
│   ├── gba/
│   ├── gbc/
│   ├── gc/
│   ├── mame/
│   ├── n3ds/
│   ├── n64/
│   ├── nds/
│   ├── ps2/
│   ├── psp/
│   ├── psvita/
│   ├── psx/
│   ├── snes/
│   ├── switch/
│   ├── wii/
│   └── wiiu/
├── data/
└── media/
```

Puedes añadir juegos desde la app: selecciona la ROM y confirma su consola;
el servidor la guarda en la carpeta correspondiente. Para varias ROMs, selecciona
todos los archivos y elige la consola una sola vez para enviar todo el lote a esa
carpeta. La app muestra el progreso y los archivos que no se hayan podido añadir.
Si copias archivos directamente
por SSH/SFTP, pulsa **Escanear biblioteca** después. En el despliegue inicial no hay ROMs.

La base de datos se guarda en `data/library.sqlite3` y las carátulas en `media/`.
Estas carpetas y `roms/` sobreviven a los reinicios y a la recreación del contenedor.

## Arranque automático

Se ha comprobado que `docker.service` está **habilitado y activo**.
El contenedor tiene esta política:

```yaml
restart: unless-stopped
```

GameClub arranca cuando Docker inicia con la Raspberry y se reinicia si su proceso
falla. Si lo detienes manualmente desde tu app de Docker, permanecerá detenido
también después de reiniciar la Raspberry hasta que vuelvas a iniciarlo.

## Control desde el móvil

En la conexión a Docker que ya tienes configurada, actualiza la lista y busca
el contenedor **`gameclub`**. Puedes iniciarlo, detenerlo, reiniciarlo y consultar
sus registros como haces con tus otros servicios.

Si la aplicación filtra por proyecto Compose, selecciona **`gameclub`** o muestra
todos los contenedores. El estado de salud esperado es **healthy**.

## Comandos de gestión por SSH

Desde el PC:

```powershell
ssh pablo@192.168.0.47
```

En la Raspberry:

```bash
cd /home/pablo/proyectos/GameClub
docker compose -p gameclub ps
docker compose -p gameclub logs -f --tail 100 gameclub
docker compose -p gameclub restart gameclub
docker compose -p gameclub stop gameclub
docker compose -p gameclub start gameclub
```

Después de actualizar el código del servidor:

```bash
cd /home/pablo/proyectos/GameClub
docker compose -p gameclub up -d --build
```

Después de cambiar variables de conexión en `.env`:

```bash
docker compose -p gameclub up -d
```

## Apps Windows y Android

Las dos versiones se han recompilado con `http://192.168.0.47:8001` como servidor
inicial. Los archivos del PC están en:

- Windows: `client/build/windows/x64/runner/Release/gameclub.exe`.
- Android móvil: `client/build/app/outputs/flutter-apk/app-mobile-release.apk`.
- Android TV: `client/build/app/outputs/flutter-apk/app-tv-release.apk`.

Si ya guardaste otra dirección en una versión anterior, cambia el servidor en
**Ajustes** a `http://192.168.0.47:8001` y pulsa **Guardar y conectar**.

## Comprobaciones realizadas

- Imagen Docker construida en la Raspberry ARM64.
- Contenedor activo y saludable, con los tres montajes persistentes comprobados.
- Docker habilitado para arrancar con el sistema.
- Política de reinicio comprobada en el contenedor.
- Detención y arranque del contenedor mediante Docker comprobados.
- API accesible desde el PC de la red local; salud y documentación devuelven HTTP 200.
- Catálogo inicial con las 16 consolas y sin juegos.
- Ejecutable Windows y APK recompilados con el puerto de este despliegue.

El arranque tras un reinicio completo de la Raspberry se basa en la configuración
verificada de Docker y del contenedor; no se ha realizado un reinicio del equipo.
Las carátulas y capturas utilizan exclusivamente Libretro y subida manual desde
0.7.1. No requieren cuenta ni claves. Al actualizar se migran los identificadores
de consola y las colas pendientes, conservando imágenes y descripciones existentes.

## Scrape masivo

Pulsa **Scrapear todos los juegos** en **Ajustes → Carátulas**. La Raspberry
ejecuta el trabajo y conserva su progreso en `data/library.sqlite3`.
Puedes cerrar la app y volver a consultar el estado desde otro dispositivo.

- Por defecto se procesan juegos sin carátula; la casilla de actualización incluye los demás.
- Se muestran progreso, contadores y los últimos 50 resultados.
- Las coincidencias ambiguas se omiten para revisión individual.
- Ante errores generales de conexión, el trabajo queda en pausa.
- Puedes cancelar tras el juego en curso y **Continuar pendientes** más adelante.
- Un reinicio del contenedor marca el trabajo como interrumpido y conserva los pendientes.

API de control: `GET/POST /api/scrape/job` y `POST /api/scrape/job/cancel`.

## Recursos arcade

Desde 0.4.1, los clientes pueden solicitar identificación de códigos históricos
por contenido mediante `arcade/cores?identify=true`. Se mantiene la API anterior
para las versiones previas. Backup previo: `data/library-before-0.4.1.sqlite3`.

La versión 0.1.3 incorpora la consulta y descarga de ZIP y discos CHD de MAME.
Las carpetas con CHD del pack se guardan debajo de `roms/mame/`, junto a los ZIP
ya existentes. GameClub mantiene esos CHD como recursos auxiliares del juego.

Desde 0.3.0, MAME utiliza MAME 2003-Plus dentro de GameClub en Windows y Android.
No se configura MAMEUI. El catálogo de compatibilidad se cachea en `data/arcade/`.
Desde 0.3.1 se añaden MAME 2003 y FBNeo con selección automática y alternativas
de arranque. Backup previo: `data/library-before-0.3.1.sqlite3`.
Consulta [MAME.md](MAME.md) para las rutas, la versión y el funcionamiento.

## Motores integrados

Desde 0.5.0 se incorpora MAME 0.232 web para tres controladores adicionales.
Los motores se cachean en `data/player/mame-web-v1/`; los clientes lo solicitan
con `web_mame=true`. Consulta [MAME_WEB.md](MAME_WEB.md). Backup previo:
`data/library-before-0.5.0.sqlite3`.

La versión 0.2.0 permite jugar a NDS y sistemas clásicos dentro de la app.
`data/player/emulatorjs-4.2.3/` almacena los recursos del motor en la Raspberry.
Se preparan automáticamente desde el CDN oficial cuando se solicitan por primera vez.
No se requiere otro servicio Docker. Consulta [PLAYER.md](PLAYER.md).

## Libretro Thumbnails

La versión 0.2.1 incorpora el proveedor sin claves para carátulas y capturas.
Los índices se cachean en `data/thumbnails/`; `data/mame_names.json` permite
resolver los códigos del pack MAMEUI a títulos. Elige Libretro en los ajustes
de carátulas para el scrape individual o masivo. Consulta [THUMBNAILS.md](THUMBNAILS.md).

Desde 0.3.0, la ficha muestra una galería independiente de capturas. Las imágenes
se guardan en `media/` y los vínculos en la tabla SQLite `screenshots`. El backup
previo al despliegue es `data/library-before-0.3.0.sqlite3`.
