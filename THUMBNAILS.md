# Carátulas y capturas sin cuenta ni claves · 0.10.3

Las carátulas se buscan automáticamente en este orden:

1. **Libretro Thumbnails**: <https://thumbnails.libretro.com/>.
2. **LaunchBox Games Database**: <https://gamesdb.launchbox-app.com/>.
3. **GameTDB**: <https://www.gametdb.com/>.
4. Si no hay coincidencia, permanece **Subir carátula** en la ficha.

Se aplica a la búsqueda individual y al lote completo. No hay cuentas, claves de
proveedor ni configuración de acceso API. ScreenScraper se retiró en 0.7.1.
Cuando una ficha tiene imagen ausente o inválida, se prueban las fuentes restantes.
Los resultados indican su procedencia; el juego guarda la fuente que realmente
aportó su carátula, aunque se haya producido un fallback al descargarla.

- Desde una ficha, pulsa **Buscar carátula** y elige el resultado correcto.
- Puedes corregir la búsqueda por el título original o en inglés.
- Para toda la biblioteca, pulsa **Scrapear todos los juegos** en Ajustes.
- Las carátulas existentes se conservan salvo que marques expresamente su actualización.
- Las carátulas usan imágenes frontales; las capturas tienen su búsqueda independiente.
- Los listados de Libretro se cachean y las peticiones se serializan.
- Las imágenes se almacenan en la Raspberry y se comparten entre tus apps.
- Las descripciones e imágenes anteriores se conservan al actualizar.

## Visual Pinball / PinMAME

Desde 0.10.3 se usa el catálogo Pinball de LaunchBox para **carátulas y capturas**.
Las máquinas físicas suelen tener Advertisement Flyer - Front en lugar de una
caja de consola: ese folleto frontal es la primera opción para la carátula.
Las cajas frontales, fanart frontal y fotografías del mueble son alternativas.
Los nombres actuales de LaunchBox con prefijo `r2_` también se reconocen.

Las capturas usan Screenshot - Gameplay y Screenshot - Game Title, con búsqueda
independiente de la carátula, hasta tres imágenes distintas y la fuente LaunchBox
identificada. No se asignan secuelas ambiguas. Se limpian extensiones VPX/VPXZ y
sufijos de autor/versión (VPW, VPX, g5k), conservando números del título como 2000.

El índice LaunchBox pasa a v3; los GameTDB mantienen v2. Se reconstruye a partir
del XML ya descargado y se invalidan las consultas antiguas de capturas vacías de
VPX. Las imágenes manuales y las carátulas ya asignadas se conservan.

Comprobación real: `tools/check_pinball_artwork.py`. El catálogo disponible tiene
3748 recursos utilizables como carátulas y 2899 capturas para la plataforma Pinball.
La Raspberry se ha actualizado y se han verificado carátulas y 18 capturas para
sus 14 mesas VPX, sin transferir juegos. La corrección sirve a las apps anteriores.

## NES y Atari 2600

Se utilizan los catálogos `Nintendo - Nintendo Entertainment System` y
`Atari - 2600`. La migración actualiza los sistemas ya registrados en SQLite,
sin volver a subir los juegos. Si la Raspberry ejecuta un servidor antiguo,
actualizar solo el APK no incorpora estos catálogos al servidor.

Se limpian extensiones, regiones, etiquetas de traducción, marcas `~` y guiones
bajos. Las búsquedas reconocen títulos compactos como `AirFortress` y `8EYES`.
Una abreviatura arbitraria como `ABOYANDH` puede requerir introducir el título
completo. Hacks, recopilatorios o juegos sin imágenes en Libretro pueden usar
**Subir carátula**. El lote omite coincidencias ambiguas y secuelas distintas.

Comprobadas búsquedas y descargas públicas reales para 1942, Super Mario Bros. 3,
Air Fortress, Pac-Man y Adventure mediante `tools/check_public_covers.py`.
La Raspberry se verificó además descargando desde las tres fuentes: 1942, Super
Mario Bros. 3 y Pac-Man en Libretro; Mario 3 y Pac-Man en LaunchBox; Super Mario
Galaxy y Mario Kart DS en GameTDB. Se comprobó el fallback real hasta la segunda y
tercera fuente en un proceso de prueba aislado, sin modificar el servicio ni las ROMs.
Pasan 73 pruebas del servidor y 26 del cliente, con análisis Flutter limpio.

## Índices de LaunchBox y GameTDB

`tools/prepare_artwork_catalogs.py` convierte los XML públicos en índices SQLite en
`data/artwork/`. El XML se procesa en streaming para limitar la memoria en la Pi;
se filtran los sistemas de GameClub, las imágenes frontales y las capturas. Las variantes y los
nombres alternativos se utilizan para buscar, conservando la consola correcta y
evitando asignar secuelas distintas automáticamente.

Los índices están precargados en la Raspberry. Si faltan, el servidor puede
prepararlos desde sus descargas públicas. La primera descarga de LaunchBox ocupa
unos 109 MB; el índice LaunchBox v3 filtrado ocupa unos 33 MB. Son metadatos, no juegos ni imágenes.
La cola antigua migra al modo automático y conserva sus pendientes. Los clientes
que todavía envían `provider=libretro` también reciben la cadena automática.

GameTDB se utiliza para GameCube, Wii, Wii U, DS, 3DS y Switch. En las consolas que
no cubre se omite esa fuente. Se prueban otros idiomas/regiones del mismo juego
si una edición no tiene imagen disponible.

## Capturas en la ficha

La ficha muestra **Capturas del juego**, procedentes de `Named_Snaps`, LaunchBox
para pinball o de tus imágenes manuales. Se agrupan versiones del mismo título y se eliminan imágenes
idénticas. Las consultas sin resultados se recuerdan siete días; **Buscar
capturas** repite la consulta. **Añadir capturas** admite varias imágenes propias,
hasta 10 MB cada una. Pulsa una captura para ampliarla con zoom.

## Arcade y atribuciones

`data/mame_names.json` relaciona códigos MAME con títulos completos. No modifica
las ROMs. Las fuentes y los créditos de imágenes son:
<https://github.com/libretro-thumbnails/libretro-thumbnails> y
<https://docs.libretro.com/guides/roms-playlists-thumbnails/>.
