package com.auto.agent.performance

import com.auto.agent.core.CommandHandler
import com.auto.agent.core.RequestContext
import com.auto.agent.core.ValidationResult
import com.auto.agent.protocol.Methods
import kotlinx.serialization.json.*

/**
 * Command handlers for performance monitoring methods.
 */
class PerfStartHandler(
    private val collector: PerformanceCollector
) : CommandHandler {
    override val method = Methods.Perf.START

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val packageName = params?.get("packageName")?.jsonPrimitive?.contentOrNull
        val metrics = params?.get("metrics")?.jsonArray?.map { it.jsonPrimitive.content }
            ?: listOf("cpu", "memory", "fps")
        val intervalMs = params?.get("intervalMs")?.jsonPrimitive?.longOrNull ?: 1000

        val sessionId = collector.startSession(packageName, metrics, intervalMs)

        return buildJsonObject {
            put("sessionId", sessionId)
        }
    }
}

class PerfStopHandler(
    private val collector: PerformanceCollector
) : CommandHandler {
    override val method = Methods.Perf.STOP

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val sessionId = params?.get("sessionId")?.jsonPrimitive?.contentOrNull
            ?: return buildJsonObject { put("error", "sessionId required") }

        val result = collector.stopSession(sessionId)
            ?: return buildJsonObject { put("error", "session not found") }

        return buildJsonObject {
            put("sessionId", result.sessionId)
            put("durationMs", result.durationMs)
            put("sampleCount", result.dataPoints.size)
            putJsonObject("summary") {
                put("avgCpu", result.summary.avgCpu)
                put("maxCpu", result.summary.maxCpu)
                put("minCpu", result.summary.minCpu)
                put("avgMemory", result.summary.avgMemory)
                put("maxMemory", result.summary.maxMemory)
                put("avgFps", result.summary.avgFps)
                put("minFps", result.summary.minFps)
                put("jankCount", result.summary.jankCount)
            }
            putJsonArray("dataPoints") {
                result.dataPoints.takeLast(1000).forEach { point ->
                    addJsonObject {
                        put("timestamp", point.timestamp)
                        point.cpu?.let { cpu ->
                            putJsonObject("cpu") {
                                put("total", cpu.totalUsage)
                                put("app", cpu.appUsage)
                            }
                        }
                        point.memory?.let { mem ->
                            putJsonObject("memory") {
                                put("totalPss", mem.totalPss)
                                put("nativePss", mem.nativePss)
                                put("dalvikPss", mem.dalvikPss)
                            }
                        }
                        point.fps?.let { fps ->
                            putJsonObject("fps") {
                                put("current", fps.currentFps)
                                put("jank", fps.jankCount)
                            }
                        }
                    }
                }
            }
        }
    }
}

class PerfSnapshotHandler(
    private val collector: PerformanceCollector
) : CommandHandler {
    override val method = Methods.Perf.SNAPSHOT

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val packageName = params?.get("packageName")?.jsonPrimitive?.contentOrNull
        val metrics = params?.get("metrics")?.jsonArray?.map { it.jsonPrimitive.content }
            ?: listOf("cpu", "memory", "fps")

        val snapshot = collector.getSnapshot(packageName, metrics)

        return buildJsonObject {
            put("timestamp", snapshot.timestamp)
            snapshot.cpu?.let { cpu ->
                putJsonObject("cpu") {
                    put("total", cpu.totalUsage)
                    put("app", cpu.appUsage)
                    put("cores", cpu.coreCount)
                }
            }
            snapshot.memory?.let { mem ->
                putJsonObject("memory") {
                    put("totalPss", mem.totalPss)
                    put("totalRam", mem.totalRam)
                    put("availableRam", mem.availableRam)
                    put("javaHeap", mem.javaHeap)
                }
            }
            snapshot.fps?.let { fps ->
                putJsonObject("fps") {
                    put("current", fps.currentFps)
                    put("jank", fps.jankCount)
                    put("bigJank", fps.bigJankCount)
                }
            }
            snapshot.network?.let { net ->
                putJsonObject("network") {
                    put("rxBytes", net.rxBytes)
                    put("txBytes", net.txBytes)
                    put("rxSpeed", net.rxSpeed)
                    put("txSpeed", net.txSpeed)
                }
            }
            snapshot.battery?.let { bat ->
                putJsonObject("battery") {
                    put("level", bat.level)
                    put("temperature", bat.temperature)
                    put("charging", bat.isCharging)
                }
            }
        }
    }
}
