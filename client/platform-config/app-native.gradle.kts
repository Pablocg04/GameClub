android {
    buildFeatures { prefab = true; buildConfig = true }
    flavorDimensions += "device"
    productFlavors {
        create("mobile") {
            dimension = "device"
            buildConfigField("String", "GAMECLUB_DEVICE", "\"mobile\"")
            manifestPlaceholders["gameclubLabel"] = "GameClub"
        }
        create("tv") {
            dimension = "device"
            buildConfigField("String", "GAMECLUB_DEVICE", "\"tv\"")
            manifestPlaceholders["gameclubLabel"] = "GameClub TV"
        }
    }
    defaultConfig {
        ndk {
            abiFilters.clear()
            abiFilters.addAll(if (providers.gradleProperty("gameclubArm64Only").orNull == "true") listOf("arm64-v8a") else listOf("armeabi-v7a", "arm64-v8a", "x86_64"))
        }
        externalNativeBuild { cmake { arguments += "-DANDROID_STL=c++_shared" } }
    }
    externalNativeBuild {
        cmake { path = file("../../native/CMakeLists.txt"); version = "3.22.1" }
    }
    sourceSets.named("main") {
        jniLibs.srcDir("../../native/vendor/pinball/jniLibs")
        assets.srcDir("../../native/vendor/pinball/assets")
    }
    packaging {
        jniLibs.keepDebugSymbols += listOf("**/libvpinball.so", "**/libpinmame.so", "**/libwinevbs.so", "**/libSDL3_image.so", "**/libSDL3_ttf.so", "**/libav*.so", "**/libsw*.so", "**/libd*.so", "**/libpupdmd.so", "**/libvni.so", "**/libfreeimage.so", "**/libaltsound.so", "**/libserum.so", "**/libsockpp.so", "**/libzedmd.so", "**/libzip.so")
    }
}
dependencies {
    implementation(files("../../native/vendor/android/SDL3-3.4.18.aar"))
}

val verifyPinballRuntime by tasks.registering {
    doLast {
        val metadata = file("../../platform-config/pinball_runtime.json")
        val vendor = file("../../native/vendor/pinball")
        check(metadata.isFile && file("${vendor.path}/assets/pinball-runtime.json").isFile) {
            "Prepara VPX Android con python tools/prepare_android_pinball.py antes de compilar."
        }
        val registry = groovy.json.JsonSlurper().parse(metadata) as Map<*, *>
        val libraries = registry["libraries"] as Map<*, *>
        for ((name, value) in libraries) {
            val entry = value as Map<*, *>
            val binary = file("${vendor.path}/jniLibs/arm64-v8a/$name")
            check(binary.isFile && binary.length() == (entry["size"] as Number).toLong()) { "Biblioteca VPX incompleta: $name" }
            val digest = MessageDigest.getInstance("SHA-256")
            binary.inputStream().use { source ->
                val bytes = ByteArray(1024 * 1024)
                while (true) { val size = source.read(bytes); if (size < 0) break; digest.update(bytes, 0, size) }
            }
            check(digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) } == entry["sha256"]) { "Huella VPX incorrecta: $name" }
        }
    }
}
tasks.named("preBuild") { dependsOn(verifyPinballRuntime) }
