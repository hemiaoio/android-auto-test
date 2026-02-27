package com.auto.agent.performance.collectors

import com.auto.agent.core.model.CpuMetrics
import java.io.File
import java.io.RandomAccessFile

/**
 * CPU usage collector.
 * - System-wide: reads /proc/stat
 * - Per-app: reads /proc/<pid>/stat
 */
class CpuCollector {

    private var lastTotal: Long = 0
    private var lastIdle: Long = 0
    private var lastAppJiffies: Long = 0

    fun collect(packageName: String?): CpuMetrics {
        val totalUsage = readSystemCpu()
        val appUsage = if (packageName != null) readAppCpu(packageName) else 0f
        val coreCount = Runtime.getRuntime().availableProcessors()

        return CpuMetrics(
            totalUsage = totalUsage,
            appUsage = appUsage,
            coreCount = coreCount,
            perCoreUsage = readPerCoreCpu()
        )
    }

    private fun readSystemCpu(): Float {
        return try {
            val line = File("/proc/stat").bufferedReader().readLine() ?: return 0f
            val parts = line.split("\\s+".toRegex()).drop(1).map { it.toLong() }
            if (parts.size < 4) return 0f

            val idle = parts[3]
            val total = parts.sum()

            val diffTotal = total - lastTotal
            val diffIdle = idle - lastIdle

            lastTotal = total
            lastIdle = idle

            if (diffTotal == 0L) 0f
            else ((diffTotal - diffIdle) * 100f / diffTotal)
        } catch (_: Exception) {
            0f
        }
    }

    private fun readAppCpu(packageName: String): Float {
        return try {
            val pid = findPid(packageName) ?: return 0f
            val statFile = File("/proc/$pid/stat")
            if (!statFile.exists()) return 0f

            val parts = statFile.readText().split(" ")
            if (parts.size < 17) return 0f

            // utime + stime (fields 14 and 15, 1-indexed)
            val utime = parts[13].toLong()
            val stime = parts[14].toLong()
            val appJiffies = utime + stime

            val diff = appJiffies - lastAppJiffies
            lastAppJiffies = appJiffies

            // Convert jiffies to percentage (assuming ~100Hz tick rate and 1s interval)
            (diff.toFloat() / Runtime.getRuntime().availableProcessors()).coerceIn(0f, 100f)
        } catch (_: Exception) {
            0f
        }
    }

    private fun readPerCoreCpu(): List<Float> {
        return try {
            File("/proc/stat").bufferedReader().useLines { lines ->
                lines.filter { it.startsWith("cpu") && it[3].isDigit() }
                    .map { line ->
                        val parts = line.split("\\s+".toRegex()).drop(1).map { it.toLong() }
                        val total = parts.sum()
                        val idle = parts.getOrElse(3) { 0L }
                        if (total == 0L) 0f else ((total - idle) * 100f / total)
                    }
                    .toList()
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun findPid(packageName: String): Int? {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", "pidof $packageName"))
            val result = process.inputStream.bufferedReader().readText().trim()
            process.waitFor()
            result.split("\\s+".toRegex()).firstOrNull()?.toIntOrNull()
        } catch (_: Exception) {
            null
        }
    }
}
