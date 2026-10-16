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
        ndk { abiFilters.addAll(listOf("armeabi-v7a", "arm64-v8a", "x86_64")) }
        externalNativeBuild { cmake { arguments += "-DANDROID_STL=c++_shared" } }
    }
    externalNativeBuild {
        cmake { path = file("../../native/CMakeLists.txt"); version = "3.22.1" }
    }
}
dependencies {
    implementation(files("../../native/vendor/android/SDL3-3.4.18.aar"))
}
