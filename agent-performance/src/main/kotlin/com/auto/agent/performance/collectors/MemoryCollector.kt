package com.auto.agent.performance.collectors

import com.auto.agent.core.model.MemoryMetrics
import java.io.File

/**
 * Memory usage collector.
 * - Per-app: parses `dumpsys meminfo <package>`
 * - System-wide: reads /proc/meminfo
 */
class MemoryCollector {

    fun collect(packageName: String?): MemoryMetrics {
        val systemMem = readSystemMemory()
        val appMem = if (packageName != null) readAppMemory(packageName) else null

        return MemoryMetrics(
            totalPss = appMem?.totalPss ?: 0,
            nativePss = appMem?.nativePss ?: 0,
            dalvikPss = appMem?.dalvikPss ?: 0,
            totalRam = systemMem.totalRam,
            availableRam = systemMem.availableRam,
            javaHeap = Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory(),
            javaHeapMax = Runtime.getRuntime().maxMemory()
        )
    }

    private fun readAppMemory(packageName: String): AppMemInfo? {
        return try {
            val process = Runtime.getRuntime().exec(
                arrayOf("sh", "-c", "dumpsys meminfo $packageName --short")
            )
            val output = process.inputStream.bufferedReader().readText()
            process.waitFor()
            parseMemInfo(output)
        } catch (_: Exception) {
            null
        }
    }

    private fun parseMemInfo(output: String): AppMemInfo {
        var totalPss = 0L
        var nativePss = 0L
        var dalvikPss = 0L

        for (line in output.lines()) {
            val trimmed = line.trim()
            when {
                trimmed.startsWith("TOTAL PSS:") || trimmed.startsWith("TOTAL:") -> {
                    totalPss = extractKb(trimmed)
                }
                trimmed.contains("Native Heap") -> {
                    nativePss = extractFirstNumber(trimmed)
                }
                trimmed.contains("Dalvik Heap") -> {
                    dalvikPss = extractFirstNumber(trimmed)
                }
            }
        }

        return AppMemInfo(totalPss, nativePss, dalvikPss)
    }

    private fun extractKb(line: String): Long {
        val match = Regex("(\\d+)").find(line.substringAfter(":"))
        return match?.value?.toLongOrNull() ?: 0
    }

    private fun extractFirstNumber(line: String): Long {
        val match = Regex("\\d+").find(line)
        return match?.value?.toLongOrNull() ?: 0
    }

    private fun readSystemMemory(): SystemMemInfo {
        return try {
            val lines = File("/proc/meminfo").readLines()
            var total = 0L
            var available = 0L
            for (line in lines) {
                when {
                    line.startsWith("MemTotal:") -> total = extractKb(line)
                    line.startsWith("MemAvailable:") -> available = extractKb(line)
                }
            }
            SystemMemInfo(total, available)
        } catch (_: Exception) {
            SystemMemInfo(0, 0)
        }
    }

    private data class AppMemInfo(val totalPss: Long, val nativePss: Long, val dalvikPss: Long)
    private data class SystemMemInfo(val totalRam: Long, val availableRam: Long)
}
