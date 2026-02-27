package com.auto.agent.root

import com.auto.agent.core.ScreenCaptureStrategy
import com.auto.agent.core.ShellExecutor
import com.auto.agent.core.model.ImageFormat
import com.auto.agent.core.model.ScreenshotConfig
import java.io.File

/**
 * Root-based screen capture using `screencap` command.
 * No user dialog required, unlike MediaProjection.
 */
class RootScreenCapture(
    private val shell: ShellExecutor,
    private val cacheDir: String
) : ScreenCaptureStrategy {

    override val name: String = "root_screencap"
    override val requiresRoot: Boolean = true

    override suspend fun capture(config: ScreenshotConfig): Result<ByteArray> {
        return try {
            val extension = when (config.format) {
                ImageFormat.PNG -> "png"
                ImageFormat.JPEG -> "jpg"
                ImageFormat.WEBP -> "webp"
            }
            val tmpFile = "$cacheDir/screenshot_${System.currentTimeMillis()}.$extension"

            val cmd = buildString {
                append("screencap -p $tmpFile")
            }

            val result = shell.executeAsRoot(cmd)
            if (result.exitCode != 0) {
                return Result.failure(RuntimeException("screencap failed: ${result.stderr}"))
            }

            val file = File(tmpFile)
            if (!file.exists()) {
                return Result.failure(RuntimeException("Screenshot file not created"))
            }

            val bytes = file.readBytes()
            file.delete()
            Result.success(bytes)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
