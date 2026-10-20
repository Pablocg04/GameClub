$ErrorActionPreference = "Stop"
if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw "Instala Flutter y añade flutter/bin al PATH antes de ejecutar este script."
}
if ((Resolve-Path ".").Path -ne $PSScriptRoot) {
    throw "Ejecuta el script desde la carpeta client: .\bootstrap.ps1"
}
$main = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "lib/main.dart"))
$pubspec = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "pubspec.yaml"))
$lockPath = Join-Path $PSScriptRoot "pubspec.lock"
$lock = if (Test-Path -LiteralPath $lockPath) { [System.IO.File]::ReadAllBytes($lockPath) } else { $null }
try {
    flutter create --no-pub --platforms=windows,android --project-name=gameclub --org=com.gameclub .
    if ($LASTEXITCODE -ne 0) { throw "No se pudo generar la estructura Flutter." }
} finally {
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "lib/main.dart"), $main)
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "pubspec.yaml"), $pubspec)
    if ($null -ne $lock) { [System.IO.File]::WriteAllBytes($lockPath, $lock) }
}
if (-not (Test-Path -LiteralPath "android/app/src/main")) { throw "Falta la carpeta Android generada." }
Copy-Item -LiteralPath "platform-config/AndroidManifest.xml" -Destination "android/app/src/main/AndroidManifest.xml" -Force
if (-not (Test-Path -LiteralPath "android/app/src/main/kotlin/com/gameclub/gameclub")) { throw "Falta la actividad Android generada." }
Copy-Item -LiteralPath "platform-config/MainActivity.kt" -Destination "android/app/src/main/kotlin/com/gameclub/gameclub/MainActivity.kt" -Force
Copy-Item -LiteralPath "platform-config/NativeGameActivity.kt" -Destination "android/app/src/main/kotlin/com/gameclub/gameclub/NativeGameActivity.kt" -Force
Copy-Item -LiteralPath "platform-config/GamepadMotion.kt" -Destination "android/app/src/main/kotlin/com/gameclub/gameclub/GamepadMotion.kt" -Force
Copy-Item -LiteralPath "platform-config/PinballActivity.kt" -Destination "android/app/src/main/kotlin/com/gameclub/gameclub/PinballActivity.kt" -Force
Copy-Item -LiteralPath "platform-config/PinballSupport.kt" -Destination "android/app/src/main/kotlin/com/gameclub/gameclub/PinballSupport.kt" -Force
if (-not (Test-Path -LiteralPath "android/app/src/main/res")) { throw "Faltan los recursos Android generados." }
if (-not (Test-Path -LiteralPath "android/app/src/main/res/xml")) { New-Item -ItemType Directory -Path "android/app/src/main/res/xml" | Out-Null }
$gradlePath = Join-Path $PSScriptRoot "android/app/build.gradle.kts"
$gradle = [System.IO.File]::ReadAllText($gradlePath)
if (-not $gradle.Contains("import java.security.MessageDigest")) { $gradle = "import java.security.MessageDigest`n`n" + $gradle }
$nativeGradle = '// GameClub native engine'
$nativeEnd = '// End GameClub native engine'
$nativeBlock = "$nativeGradle`n" + [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "platform-config/app-native.gradle.kts")).TrimEnd() + "`n$nativeEnd`n"
if ($gradle.Contains($nativeEnd)) {
    $start = $gradle.IndexOf($nativeGradle)
    $end = $gradle.IndexOf($nativeEnd, $start) + $nativeEnd.Length
    $gradle = $gradle.Substring(0, $start) + $nativeBlock + $gradle.Substring($end)
} elseif ($gradle.Contains($nativeGradle)) {
    # Migración del bloque gestionado por bootstrap en 0.6.0 (al final del archivo).
    $start = $gradle.IndexOf($nativeGradle)
    if ($gradle.Substring($start) -notmatch '(?s)^// GameClub native engine\s+android \{.*?dependencies \{\s+implementation\(files\("../../native/vendor/android/SDL3-3.4.18.aar"\)\)\s*\}\s*$') { throw "El bloque nativo generado tiene cambios no reconocidos." }
    $gradle = $gradle.Substring(0, $start) + $nativeBlock
} else { $gradle += "`n$nativeBlock" }
[System.IO.File]::WriteAllText($gradlePath, $gradle)
if (-not (Test-Path -LiteralPath "android/app/src/tv")) { New-Item -ItemType Directory -Path "android/app/src/tv" | Out-Null }
Copy-Item -LiteralPath "platform-config/AndroidManifest-tv.xml" -Destination "android/app/src/tv/AndroidManifest.xml" -Force
Copy-Item -LiteralPath "platform-config/gameclub_banner.xml" -Destination "android/app/src/main/res/drawable/gameclub_banner.xml" -Force
$cmakePath = Join-Path $PSScriptRoot "windows/CMakeLists.txt"
$cmake = [System.IO.File]::ReadAllText($cmakePath)
$compat = 'include("${CMAKE_CURRENT_SOURCE_DIR}/../platform-config/windows-compat.cmake")'
if (-not $cmake.Contains($compat)) {
    $anchor = 'include(flutter/generated_plugins.cmake)'
    if (-not $cmake.Contains($anchor)) { throw "No se encontró el punto de configuración de plugins Windows." }
    [System.IO.File]::WriteAllText($cmakePath, $cmake.Replace($anchor, "$anchor`n$compat"))
}
$cmake = [System.IO.File]::ReadAllText($cmakePath)
$nativeCmake = 'add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../native" "${CMAKE_CURRENT_BINARY_DIR}/native")'
if (-not $cmake.Contains($nativeCmake)) {
    [System.IO.File]::WriteAllText($cmakePath, $cmake + "`n$nativeCmake`n")
}
# El test generado por Flutter comprueba su contador de ejemplo; GameClub usa otro inicio.
if (Test-Path -LiteralPath "test/widget_test.dart") {
    $generated = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "test/widget_test.dart"))
    if ($generated.Contains("Counter increments smoke test")) { Remove-Item -LiteralPath "test/widget_test.dart" }
}
flutter pub get
if ($LASTEXITCODE -ne 0) { throw "No se pudieron preparar las dependencias. Si Flutter indica que necesita symlinks, activa el Modo de desarrollador de Windows y vuelve a ejecutar el script." }
