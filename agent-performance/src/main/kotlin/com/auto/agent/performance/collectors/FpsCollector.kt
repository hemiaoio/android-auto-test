package com.auto.agent.performance.collectors

import com.auto.agent.core.model.FpsMetrics

/**
 * FPS collector.
 * - Root mode: parses `dumpsys SurfaceFlinger --latency <window>`
 * - Non-root: uses Choreographer frame callback (limited to own process)
 */
class FpsCollector {

    private var lastFrameTimestamps = mutableListOf<Long>()
    private val frameWindow = 120 // Track last 120 frames (~2 seconds at 60fps)

    // Jank threshold: frame taking > 2x of target frame time (16.67ms * 2)
    private val jankThresholdNs = 33_340_000L
    private val bigJankThresholdNs = 66_680_000L

    fun collect(packageName: String?): FpsMetrics {
        return if (packageName != null) {
            collectViaSurfaceFlinger(packageName)
        } else {
            FpsMetrics(currentFps = 0f, avgFps = 0f, jankCount = 0, bigJankCount = 0)
        }
    }

    private fun collectViaSurfaceFlinger(packageName: String): FpsMetrics {
        return try {
            val process = Runtime.getRuntime().exec(
                arrayOf("sh", "-c", "dumpsys SurfaceFlinger --latency \"SurfaceView - $packageName\"")
            )
            val output = process.inputStream.bufferedReader().readText()
            process.waitFor()

            if (process.exitValue() != 0 || output.isBlank()) {
                return collectViaGfxInfo(packageName)
            }

            parseSurfaceFlingerOutput(output)
        } catch (_: Exception) {
            collectViaGfxInfo(packageName)
        }
    }

    private fun parseSurfaceFlingerOutput(output: String): FpsMetrics {
        val lines = output.lines().drop(1) // Skip first line (refresh period)
        val timestamps = mutableListOf<Long>()

        for (line in lines) {
            val parts = line.trim().split("\\s+".toRegex())
            if (parts.size >= 3) {
                val desiredPresent = parts[2].toLongOrNull() ?: continue
                if (desiredPresent > 0) {
                    timestamps.add(desiredPresent)
                }
            }
        }

        if (timestamps.size < 2) {
            return FpsMetrics(currentFps = 0f, avgFps = 0f, jankCount = 0, bigJankCount = 0)
        }

        val frameTimes = mutableListOf<Long>()
        var jankCount = 0
        var bigJankCount = 0

        for (i in 1 until timestamps.size) {
            val frameTime = timestamps[i] - timestamps[i - 1]
            frameTimes.add(frameTime)
            if (frameTime > jankThresholdNs) jankCount++
            if (frameTime > bigJankThresholdNs) bigJankCount++
        }

        val totalDurationNs = timestamps.last() - timestamps.first()
        val currentFps = if (totalDurationNs > 0) {
            (timestamps.size - 1) * 1_000_000_000f / totalDurationNs
        } else 0f

        return FpsMetrics(
            currentFps = currentFps,
            avgFps = currentFps,
            jankCount = jankCount,
            bigJankCount = bigJankCount,
            frameTimes = frameTimes.takeLast(frameWindow)
        )
    }

    /**
     * Fallback: use `dumpsys gfxinfo` for frame stats
     */
    private fun collectViaGfxInfo(packageName: String): FpsMetrics {
        return try {
            val process = Runtime.getRuntime().exec(
                arrayOf("sh", "-c", "dumpsys gfxinfo $packageName framestats")
            )
            val output = process.inputStream.bufferedReader().readText()
            process.waitFor()
            parseGfxInfoOutput(output)
        } catch (_: Exception) {
            FpsMetrics(currentFps = 0f, avgFps = 0f, jankCount = 0, bigJankCount = 0)
        }
    }

    private fun parseGfxInfoOutput(output: String): FpsMetrics {
        var totalFrames = 0
        var jankFrames = 0

        for (line in output.lines()) {
            val trimmed = line.trim()
            when {
                trimmed.startsWith("Total frames rendered:") -> {
                    totalFrames = trimmed.substringAfter(":").trim().toIntOrNull() ?: 0
                }
                trimmed.startsWith("Janky frames:") -> {
                    val match = Regex("(\\d+)").find(trimmed.substringAfter(":"))
                    jankFrames = match?.value?.toIntOrNull() ?: 0
                }
            }
        }

        return FpsMetrics(
            currentFps = 0f, // gfxinfo doesn't give real-time FPS
            avgFps = 0f,
            jankCount = jankFrames,
            bigJankCount = 0
        )
    }
}
