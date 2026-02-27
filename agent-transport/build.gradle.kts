plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.auto.agent.transport"
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
    implementation(project(":agent-protocol"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:${property("COROUTINES_VERSION")}")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:${property("SERIALIZATION_VERSION")}")

    // Ktor Server (embedded WebSocket)
    implementation("io.ktor:ktor-server-core:${property("KTOR_VERSION")}")
    implementation("io.ktor:ktor-server-netty:${property("KTOR_VERSION")}")
    implementation("io.ktor:ktor-server-websockets:${property("KTOR_VERSION")}")
    implementation("io.ktor:ktor-server-content-negotiation:${property("KTOR_VERSION")}")
    implementation("io.ktor:ktor-serialization-kotlinx-json:${property("KTOR_VERSION")}")
}
