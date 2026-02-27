package com.auto.agent.performance.collectors

import com.auto.agent.core.model.NetworkMetrics
import java.io.File

/**
 * Network traffic collector.
 * Reads /proc/net/dev for system-wide stats, or per-UID stats from /proc/net/xt_qtaguid/stats.
 */
class NetworkCollector {

    private var lastRxBytes: Long = 0
    private var lastTxBytes: Long = 0
    private var lastTimestamp: Long = 0

    fun collect(): NetworkMetrics {
        val (rxBytes, txBytes) = readNetDevTotal()
        val now = System.currentTimeMillis()

        val elapsed = (now - lastTimestamp).coerceAtLeast(1)
        val rxSpeed = if (lastTimestamp > 0) ((rxBytes - lastRxBytes) * 1000 / elapsed) else 0
        val txSpeed = if (lastTimestamp > 0) ((txBytes - lastTxBytes) * 1000 / elapsed) else 0

        lastRxBytes = rxBytes
        lastTxBytes = txBytes
        lastTimestamp = now

        return NetworkMetrics(
            rxBytes = rxBytes,
            txBytes = txBytes,
            rxSpeed = rxSpeed,
            txSpeed = txSpeed
        )
    }

    private fun readNetDevTotal(): Pair<Long, Long> {
        return try {
            var totalRx = 0L
            var totalTx = 0L

            File("/proc/net/dev").bufferedReader().useLines { lines ->
                lines.drop(2).forEach { line ->
                    val parts = line.trim().split("\\s+".toRegex())
                    if (parts.size >= 10) {
                        val iface = parts[0].trimEnd(':')
                        // Skip loopback
                        if (iface != "lo") {
                            totalRx += parts[1].toLongOrNull() ?: 0
                            totalTx += parts[9].toLongOrNull() ?: 0
                        }
                    }
                }
            }

            Pair(totalRx, totalTx)
        } catch (_: Exception) {
            Pair(0L, 0L)
        }
    }
}
