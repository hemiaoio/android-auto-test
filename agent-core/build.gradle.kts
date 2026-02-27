plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.auto.agent.core"
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
    api(project(":agent-protocol"))
    api(project(":agent-transport"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:${property("COROUTINES_VERSION")}")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:${property("COROUTINES_VERSION")}")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:${property("SERIALIZATION_VERSION")}")
    implementation("io.insert-koin:koin-android:${property("KOIN_VERSION")}")
}
