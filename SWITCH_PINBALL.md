# Visual Pinball + PinMAME para Switch · GameClub 0.13.0

Port nativo experimental para Horizon/libnx. Incluye el reproductor de Visual
Pinball X, la biblioteca de emulación PinMAME y los complementos estáticos
PinMAME, B2S y FlexDMD. No es un core de RetroArch ni necesita Android en Switch.

La compilación y las comprobaciones de formato no certifican el funcionamiento
en hardware. El primer arranque, vídeo, audio, mandos y rendimiento de las mesas
se deben comprobar en una Switch física. No se incluyen mesas, ROMs ni BIOS.

## Instalación y primera prueba

1. Extrae `GameClub-Switch-Pinball-0.13.0.zip` en la raíz de la SD. Quedarán
   `switch/gameclub/GameClub-Switch.nro` y
   `switch/gameclub/pinball/GameClubPinball.nro`, junto a los recursos del motor.
2. Conserva todos los archivos de `switch/gameclub/pinball/`. Copiar solo el NRO
   del motor no instala sus scripts, imágenes, fuentes ni shaders.
3. Abre Homebrew Menu con acceso completo a memoria, manteniendo R al abrir un
   juego instalado, como indica la [guía de Libretro](https://docs.libretro.com/guides/install-libnx/).
4. Abre **GameClub**, conecta con la Raspberry y recarga la biblioteca con −.
5. Busca una mesa en **vpinball** y pulsa A. GameClub muestra por separado
   consulta, descarga, extracción y apertura del motor, con progreso de los
   archivos. B cancela la preparación; una descarga ya completa se reutiliza.
   Comprueba tamaños/CRC y prepara mesa, scripts y ROMs antes de iniciar el motor.
6. Espera a que termine la primera carga. Si aparece una pantalla de
   inicialización de la máquina, los botones de servicio están disponibles
   pulsando los sticks. Su configuración se guarda en NVRAM para siguientes usos.

Los otros sistemas conservan sus núcleos de RetroArch. El paquete de pinball no
los sustituye ni incluye. La Raspberry sigue sirviendo los mismos paquetes de
mesas; no es necesario reinstalar el servidor para esta ruta de reproducción.

## Controles iniciales

| Botón | Acción |
|---|---|
| L / ZL | Flipper izquierdo |
| R / ZR | Flipper derecho |
| A | Lanzar bola; confirmar en menús |
| X / − | Insertar moneda |
| Y | Iniciar partida |
| B / + | Atrás; abrir o cerrar el menú del motor |
| Cruceta | Desplazarse por el menú |
| Pulsar stick izquierdo / derecho | Teclas de servicio 7 / 8 |

El menú incluye **Salir**. Cada apertura arranca una emulación nueva y carga la
mesa desde el principio. No se crean ni restauran instantáneas de partida.
Se conserva NVRAM, configuración de la máquina y ajustes del reproductor por mesa.
Al cerrar el motor se vuelve al entorno homebrew; abre GameClub de nuevo.

## Registros para la prueba física

`sd:/switch/gameclub/pinball-prepare.log` registra las fases del lanzador,
errores de preparación y el resultado de la apertura del NRO. Si GameClub queda
visible sin entrar en el motor, consulta primero este archivo. El lanzador
comprueba que Homebrew Menu tenga acceso completo a memoria antes de descargar.
`sd:/switch/gameclub/pinball-start.log` confirma que el motor ha llegado a su
punto de entrada, antes de abrir las preferencias privadas de la mesa.

Cada mesa tiene una carpeta privada bajo:

`sd:/switch/gameclub/libraries/<servidor>/pinball-state/<id-mesa>/`

- `switch-player.log`: registro de arranque y errores del motor.
- `VPinballX.ini`: ajustes iniciales de imagen y del reproductor.
- `nvram/`, `cfg/`, `hi/`: configuración de PinMAME, separada de la caché.
- Los registros adicionales de VPX se encuentran en la misma carpeta de
  preferencias o su subcarpeta de versión.

Para diagnosticar un fallo, hacen falta el nombre de la mesa, el punto en que
ocurre (antes del menú, al descargar o al abrir la mesa) y el contenido del
registro. Los paquetes originales de la Raspberry no se modifican.

## Alcance y límites

- Se solicitan OpenGL 4.3 y una imagen de 1280×720. La configuración inicial
  limita las texturas a 1024 y desactiva MSAA/FXAA para reducir el consumo.
- Se integra una sola pantalla. No se abren ventanas externas de backglass.
- PinMAME se compila sin Pinball 2000, Spike ni recompilador JIT. Las máquinas
  clásicas del núcleo permanecen disponibles; una mesa puede requerir funciones,
  scripts u otros complementos que esta primera integración no proporcione.
- PUP, DOF, colorizadores externos y dispositivos de cabinet no se incluyen.
- No se garantiza que todas las mesas del catálogo sean compatibles ni que
  alcancen una velocidad determinada. La prueba física decide la compatibilidad.
- TV continúa sin Visual Pinball. PC y móvil conservan sus motores anteriores.
- La primera prueba del propietario confirmó que GameClub abre, pero informó de
  bloqueo al preparar/iniciar un pinball. Esta revisión añade escritura con
  búfer, progreso de extracción, cancelación y registros para localizarlo. No se
  considera resuelta la ejecución de mesas hasta repetir la prueba física.

## Reproducir la compilación

En Windows con Python 3.14, Pillow, Git y CMake/Ninja:

```powershell
.\.venv\Scripts\python.exe tools/prepare_switch_pinball.py
.\.venv\Scripts\python.exe tools/build_switch_pinball.py all
.\.venv\Scripts\python.exe tools/build_switch.py
.\.venv\Scripts\python.exe tools/package_switch_pinball.py
```

`switch-pinball/upstream.json` fija cada revisión. Los cambios a proyectos externos
están en `switch-pinball/patches/`; las fuentes y objetos se preparan en
`dist/switch-ports`. Los paquetes del SDK se verifican por SHA-256 y quedan
aislados en el proyecto. Se conservan sus licencias y las de los motores.
