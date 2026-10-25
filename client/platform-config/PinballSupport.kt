package com.gameclub.gameclub

import android.app.ActivityManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import java.io.File

object PinballSupport {
    fun capabilities(context: Context): Map<String, Any> {
        if (BuildConfig.GAMECLUB_DEVICE == "tv") return mapOf(
            "compatible" to false, "integrated" to false,
            "reason" to "Visual Pinball no está disponible en la variante TV de GameClub.",
            "abi" to File(context.applicationInfo.nativeLibraryDir).name, "androidApi" to Build.VERSION.SDK_INT)
        val bundled = runCatching { context.assets.open("pinball-runtime.json").close(); true }.getOrDefault(false)
        val arm64 = File(context.applicationInfo.nativeLibraryDir).name == "arm64"
        val gles = (context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).deviceConfigurationInfo.reqGlEsVersion
        val vulkan = context.packageManager.hasSystemFeature(PackageManager.FEATURE_VULKAN_HARDWARE_LEVEL)
        val reason = when {
            !bundled -> "Este paquete de GameClub no incluye el motor pinball. Instala el APK completo actualizado."
            Build.VERSION.SDK_INT < 33 -> "El pinball integrado necesita Android 13 o posterior."
            !arm64 -> "El motor pinball integrado necesita un proceso Android ARM64."
            gles < 0x30002 && !vulkan -> "El motor pinball necesita OpenGL ES 3.2 o Vulkan."
            else -> ""
        }
        return mapOf("compatible" to reason.isEmpty(), "integrated" to bundled, "reason" to reason,
            "abi" to File(context.applicationInfo.nativeLibraryDir).name, "androidApi" to Build.VERSION.SDK_INT,
            "backend" to if (gles >= 0x30002) "OpenGLES" else "Vulkan")
    }
}
