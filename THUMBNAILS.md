# Carátulas y capturas sin cuenta ni claves · 0.8.0

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
se filtran los sistemas de GameClub y las imágenes frontales. Las variantes y los
nombres alternativos se utilizan para buscar, conservando la consola correcta y
evitando asignar secuelas distintas automáticamente.

Los índices están precargados en la Raspberry. Si faltan, el servidor puede
prepararlos desde sus descargas públicas. La primera descarga de LaunchBox ocupa
unos 109 MB; el índice filtrado ocupa unos 21 MB. Son metadatos, no juegos ni imágenes.
La cola antigua migra al modo automático y conserva sus pendientes. Los clientes
que todavía envían `provider=libretro` también reciben la cadena automática.

GameTDB se utiliza para GameCube, Wii, Wii U, DS, 3DS y Switch. En las consolas que
no cubre se omite esa fuente. Se prueban otros idiomas/regiones del mismo juego
si una edición no tiene imagen disponible.

## Capturas en la ficha

La ficha muestra **Capturas del juego**, procedentes de `Named_Snaps` o de tus
imágenes manuales. Se agrupan versiones del mismo título y se eliminan imágenes
idénticas. Las consultas sin resultados se recuerdan siete días; **Buscar
capturas** repite la consulta. **Añadir capturas** admite varias imágenes propias,
hasta 10 MB cada una. Pulsa una captura para ampliarla con zoom.

## Arcade y atribuciones

`data/mame_names.json` relaciona códigos MAME con títulos completos. No modifica
las ROMs. Las fuentes y los créditos de imágenes son:
<https://github.com/libretro-thumbnails/libretro-thumbnails> y
<https://docs.libretro.com/guides/roms-playlists-thumbnails/>.
