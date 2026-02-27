plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.auto.agent.protocol"
    compileSdk = property("COMPILE_SDK").toString().toInt()

    defaultConfig {
        minSdk = property("MIN_SDK").toString().toInt()
        consumerProguardFiles("consumer-rules.pro")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:${property("SERIALIZATION_VERSION")}")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:${property("COROUTINES_VERSION")}")
}
