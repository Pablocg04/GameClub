# GameClub · cliente

Aplicación Flutter para Windows y Android. Consulta el [README principal](../README.md)
para configurar la Raspberry, las carátulas públicas de Libretro y las herramientas de compilación.

Desde esta carpeta, con Flutter instalado:

```powershell
.\bootstrap.ps1
flutter analyze
flutter test
flutter run -d windows
```

El script genera las carpetas nativas de Windows y Android, conserva el código
de la app y aplica el manifiesto Android preparado para la red local.
Las carpetas nativas generadas no se incluyen en Git; la configuración personalizada
se conserva en `platform-config/`.
