# MAME 0.232 web por controlador · GameClub 0.5.0

Documento histórico. Desde 0.6.0 la aplicación abre estos juegos mediante
[MAME nativo](MAME_NATIVE.md).

Motor adicional integrado en GameClub, independiente de EmulatorJS/Libretro.
Usa las compilaciones WebAssembly de MAME 0.232 publicadas para Emularity.

## Cobertura inicial comprobada

| Juego | Controlador |
|---|---|
| Barline (`barline`) | `nbmj8688` |
| Casino Fever 6.1 (`cfever61`) | `highvdeo` |
| Royal Casino (`rcasino`) | `caswin` |

Los tres ZIP del pack original se han ejecutado con vídeo real en Windows y en
Google TV API 36 emulado. Este motor se añade como candidato automático mediante
`arcade/cores?identify=true&web_mame=true` y se recuerda cuando arranca.
La versión 0.5.0 solo registra estos tres juegos en el motor adicional: ampliar
otros controladores exige comprobar sus ROMs y controles, no se promete cobertura total.

## Motores y caché

Se descargan únicamente los motores, desde
`https://archive.org/download/emularity_engine_v1/`. Los archivos comprimidos se
verifican contra las huellas fijas de `server/app/mame_web.py`, se descomprimen y
se conservan en `data/player/mame-web-v1/` en la Raspberry. La app conserva su
caché local y ejecuta la emulación en el dispositivo. Las ROMs proceden únicamente
de la biblioteca del usuario.

API de recursos: `GET /api/player/mame-web/<controlador>/<archivo>`.
Solo se admiten los seis archivos JS/WASM de los tres controladores registrados.

## Controles

- PC: **5** moneda, **1** inicio/repartir, **2** apuesta y **Z/X/C/V/B** cartas.
- Mando estándar: Select moneda, Start inicio, A/B/X/Y/L1 para las cinco cartas,
  R1 apuesta y cruceta para navegación.
- Móvil: botones táctiles para moneda, inicio, apuesta, cartas y cruceta.
- **Configurar controles MAME** en la barra superior abre la configuración nativa;
  **Tab** también permite abrirla en PC. Las asignaciones del juego se pueden ajustar allí.
- En TV, la opción está en el menú abierto con Start + Select. Mientras está
  abierta la configuración de MAME, A acepta, B retrocede y la cruceta navega.
- Vuelve a pulsar Configurar para cerrar la configuración y volver al juego.

Las teclas son una asignación inicial para estos juegos de cartas/apuestas;
los puertos de entrada de cada máquina pueden requerir ajustes específicos.

## Guardados

NVRAM, configuración de controles y archivos de estado existentes se guardan
localmente en un ZIP separado para `mame_web`. Al cerrar, MAME termina su máquina,
escribe sus archivos y la app confirma el almacenamiento antes de volver.
Al abrir, se restauran en `/nvram`, `/cfg` y `/sta`.

Esto no añade estados instantáneos a máquinas que no los soportan ni sincroniza
partidas entre dispositivos. Los puntos/ajustes que conserva cada máquina
dependen de sus archivos NVRAM y de su propia emulación.

## Verificación

- 50 pruebas del servidor y 14 del cliente.
- `client/integration_test/mame_web_test.dart`: tres juegos reales en Windows y
  tres en Google TV emulado, con vídeo, teclado, pausa y guardado al salir.
- `tools/probe_mame_web.py`: banco de desarrollo aislado para los motores.
- `tools/run_tv_input_test.py --target integration_test/mame_web_test.dart`:
  repetición de la prueba en el AVD Google TV preparado por el proyecto.
- El rendimiento y el perfil de un mando Bluetooth físico en la tele del usuario
  siguen pendientes de comprobar en ese equipo.

MAME 0.232 y sus componentes conservan sus licencias. Consulta
`THIRD_PARTY_NOTICES.md` para fuentes y atribuciones.
