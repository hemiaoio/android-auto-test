plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.auto.agent.accessibility"
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
    implementation(project(":agent-core"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:${property("COROUTINES_VERSION")}")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:${property("COROUTINES_VERSION")}")
}
