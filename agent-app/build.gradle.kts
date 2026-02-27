plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.auto.agent.app"
    compileSdk = property("COMPILE_SDK").toString().toInt()

    defaultConfig {
        applicationId = "com.auto.agent"
        minSdk = property("MIN_SDK").toString().toInt()
        targetSdk = property("TARGET_SDK").toString().toInt()
        versionCode = property("VERSION_CODE").toString().toInt()
        versionName = property("VERSION_NAME").toString()
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation(project(":agent-core"))
    implementation(project(":agent-accessibility"))
    implementation(project(":agent-root"))
    implementation(project(":agent-performance"))
    implementation(project(":agent-transport"))

    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:${property("COROUTINES_VERSION")}")
    implementation("io.insert-koin:koin-android:${property("KOIN_VERSION")}")
}
