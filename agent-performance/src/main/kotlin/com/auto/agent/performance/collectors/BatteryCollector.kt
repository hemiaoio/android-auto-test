package com.auto.agent.performance.collectors

import com.auto.agent.core.model.BatteryMetrics
import java.io.File

/**
 * Battery status collector.
 * Reads from /sys/class/power_supply/battery/ for direct access,
 * falls back to `dumpsys battery` parsing.
 */
class BatteryCollector {

    fun collect(): BatteryMetrics {
        return readFromSysFs() ?: readFromDumpsys() ?: BatteryMetrics(
            level = -1,
            temperature = 0f,
            voltage = 0,
            isCharging = false,
            currentNow = 0
        )
    }

    private fun readFromSysFs(): BatteryMetrics? {
        return try {
            val base = "/sys/class/power_supply/battery"
            val level = readSysFile("$base/capacity")?.toIntOrNull() ?: return null
            val temp = (readSysFile("$base/temp")?.toFloatOrNull() ?: 0f) / 10f
            val voltage = readSysFile("$base/voltage_now")?.toIntOrNull()?.let { it / 1000 } ?: 0
            val status = readSysFile("$base/status") ?: ""
            val current = readSysFile("$base/current_now")?.toLongOrNull() ?: 0

            BatteryMetrics(
                level = level,
                temperature = temp,
                voltage = voltage,
                isCharging = status.equals("Charging", ignoreCase = true) ||
                        status.equals("Full", ignoreCase = true),
                currentNow = current
            )
        } catch (_: Exception) {
            null
        }
    }

    private fun readFromDumpsys(): BatteryMetrics? {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", "dumpsys battery"))
            val output = process.inputStream.bufferedReader().readText()
            process.waitFor()

            var level = 0
            var temperature = 0f
            var voltage = 0
            var isCharging = false

            for (line in output.lines()) {
                val trimmed = line.trim()
                when {
                    trimmed.startsWith("level:") ->
                        level = trimmed.substringAfter(":").trim().toIntOrNull() ?: 0
                    trimmed.startsWith("temperature:") ->
                        temperature = (trimmed.substringAfter(":").trim().toFloatOrNull() ?: 0f) / 10f
                    trimmed.startsWith("voltage:") ->
                        voltage = trimmed.substringAfter(":").trim().toIntOrNull() ?: 0
                    trimmed.startsWith("status:") -> {
                        val statusVal = trimmed.substringAfter(":").trim().toIntOrNull() ?: 0
                        isCharging = statusVal == 2 || statusVal == 5 // CHARGING or FULL
                    }
                }
            }

            BatteryMetrics(
                level = level,
                temperature = temperature,
                voltage = voltage,
                isCharging = isCharging,
                currentNow = 0
            )
        } catch (_: Exception) {
            null
        }
    }

    private fun readSysFile(path: String): String? {
        return try {
            File(path).readText().trim()
        } catch (_: Exception) {
            null
        }
    }
}
