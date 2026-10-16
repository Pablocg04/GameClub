# Arcade automático · GameClub 0.6.0

La implementación actual utiliza MAME/FBNeo **nativos** en Android, Android TV y
Windows. Instalación, controles, catálogo histórico y pruebas:
[MAME_NATIVE.md](MAME_NATIVE.md).

## Histórico técnico de la ruta web · 0.5.0

El contenido siguiente documenta la implementación anterior.

Los juegos arcade se reproducen dentro de GameClub en Windows y Android con
EmulatorJS 4.2.3. No se configura un ejecutable externo.

## Núcleos

| Núcleo | Base |
|---|---|
| MAME 2003-Plus | MAME 0.78 con ampliaciones |
| MAME 2003 | MAME 0.78 |
| FinalBurn Neo | Catálogo arcade de FBNeo |
| MAME web por controlador | MAME 0.232, cobertura inicial de tres juegos |

El pack original corresponde a MAME 0.130u3; ninguno de estos núcleos es esa
versión exacta. Tener varios núcleos amplía la cobertura pero no garantiza que
todos los romsets sean compatibles. Killer Instinct del pack actual sigue sin
una combinación compatible entre los núcleos disponibles.

## Selección y arranque

1. La Raspberry consulta los catálogos de cada núcleo y compara chips por
   CRC/tamaño, resolviendo padres y BIOS.
2. Los núcleos con chips de juego incompatibles se omiten con un motivo explícito.
   FBNeo realiza la validación final de sus BIOS alternativas y componentes
   opcionales durante el arranque.
3. La app prepara los recursos del primer candidato y abre el reproductor.
4. Si falla o no avanza la emulación, prueba el siguiente candidato sin pedir
   de nuevo **Iniciar juego**. Cada candidato se intenta una sola vez.
5. Se recuerda el núcleo que arranca por juego, servidor y plataforma. Un cambio
   de ROMs/dependencias o de versión del motor invalida esa preferencia.
6. Si ninguno funciona, se muestran los motivos de todos los intentos.

La verificación no confunde la pantalla **FBNeo Error** con un juego iniciado:
se reconoce la cabecera del error del núcleo fijado a 4.2.3 antes de recordar el
resultado. Los errores del motor y los límites de espera también activan el
cambio de núcleo. La comprobación acredita el arranque, no garantiza que todas
las escenas del juego estén perfectamente emuladas ni una velocidad concreta.

## Archivos y controles

- ZIP principal, padres y BIOS se conservan sin extraer en la caché local.
- Los CHD se preparan cuando el catálogo los requiere y están disponibles;
  el núcleo debe admitir la versión del disco.
- Carpeta de caché: `Documentos/GameClub/arcade/<servidor>/` en Windows y
  documentos privados de la app en Android.
- Los recursos se montan en `/roms/` dentro del motor. El adaptador convierte
  ArrayBuffer a Uint8Array al escribir los recursos externos de EmulatorJS 4.2.3.
- Guardados y estados separados por núcleo, para evitar mezclar formatos.
- Teclado predeterminado: **V** introduce moneda y **Enter** inicia la partida.
  Los botones táctiles y **Ajustes de Control** permiten usar Select/Start y mandos.
- El reproductor permite audio automático para que un cambio de núcleo no quede
  detenido esperando otra pulsación por la política de reproducción del navegador.

## Catálogos fijados

Se cachean en `data/arcade/`:

- MAME 2003-Plus: commit `c1de17eb547a618b99754a3d708a07dd77a42021`.
- MAME 2003: commit `ef6a38e7b56efb67607ab5875ea02a09517b4a19`.
- FBNeo: commit `e8291a39f637d23900d6998ea7f67648856201f9`.

Son los catálogos publicados antes de la compilación del motor de junio de 2025;
la validación definitiva la realiza el núcleo distribuido por EmulatorJS.

## API

- `GET /api/games/<id>/arcade/cores?identify=true&web_mame=true`: candidatos con identificación por contenido y MAME web adicional.
- Sin `identify=true`, se conserva la comprobación por código para clientes anteriores.
- `GET /api/games/<id>/arcade`: plan anterior de MAME 2003-Plus, conservado para clientes 0.3.0.
- `GET /api/mame/download?path=<ruta>`: recursos de la biblioteca.
- `GET /api/player`: motores y núcleos arcade disponibles.

## Comprobaciones reales en Windows

- Metal Slug del pack original: FBNeo, BIOS preparada y vídeo real de 304×224.
- Street Fighter II: cambio automático desde un fallo simulado al núcleo
  MAME 2003-Plus, vídeo de 384×224 y preferencia recordada.
- Metal Slug sin BIOS en una prueba aislada: se detecta la pantalla de error y
  no se registra un éxito.

Estas pruebas están en `client/integration_test/multi_arcade_test.dart`.

## Códigos históricos y revisiones del romset

Desde 0.4.1, si el código del ZIP no coincide, se comparan CRC/tamaño con otras
entradas del catálogo. Una coincidencia parcial de gráficos o una BIOS compartida
no se acepta como identidad del juego: debe cubrir al menos el 80 % de los bytes
de chips del ZIP y superar la auditoría completa del candidato.

El ZIP se descarga con el nombre que necesita el núcleo, sin renombrar ni alterar
el original en la Raspberry. La biblioteca, el título y los favoritos mantienen
el identificador del juego original.

Caso verificado: `sbasketb.zip` del pack 0.130u3 contiene la versión H de Super
Basketball. FBNeo la identifica como `sbasketh`, mientras que su código `sbasketb`
corresponde a la versión I. Se ha ejecutado la versión H con vídeo real de 256×224
en WebView2. Prueba: `client/integration_test/arcade_identity_test.dart`.

Barline no está incluido en los tres núcleos Libretro anteriores. Desde 0.5.0
se ejecuta mediante el motor MAME 0.232 web `nbmj8688`; también se incorporan
Casino Fever 6.1 (`highvdeo`) y Royal Casino (`caswin`). Consulta [MAME_WEB.md](MAME_WEB.md).
