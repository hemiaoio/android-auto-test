package com.auto.agent.core.model

import kotlinx.serialization.Serializable

@Serializable
data class DeviceInfo(
    val model: String,
    val manufacturer: String,
    val brand: String,
    val sdkVersion: Int,
    val androidVersion: String,
    val abi: String,
    val screenWidth: Int,
    val screenHeight: Int,
    val density: Float,
    val isRooted: Boolean,
    val isAccessibilityEnabled: Boolean,
    val serial: String,
    val buildFingerprint: String
)

@Serializable
data class ShellResult(
    val exitCode: Int,
    val stdout: String,
    val stderr: String
)

@Serializable
data class ScreenshotConfig(
    val format: ImageFormat = ImageFormat.PNG,
    val quality: Int = 100,
    val scale: Float = 1.0f
)

@Serializable
enum class ImageFormat {
    PNG, JPEG, WEBP
}
