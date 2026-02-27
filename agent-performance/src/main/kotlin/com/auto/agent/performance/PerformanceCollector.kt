package com.auto.agent.performance

import com.auto.agent.core.model.PerfMetrics
import com.auto.agent.performance.collectors.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

/**
 * Coordinates multiple metric collectors and manages performance sessions.
 */
class PerformanceCollector(
    private val cpuCollector: CpuCollector,
    private val memoryCollector: MemoryCollector,
    private val fpsCollector: FpsCollector,
    private val networkCollector: NetworkCollector,
    private val batteryCollector: BatteryCollector
) {
    private val sessions = ConcurrentHashMap<String, PerfSessionRunner>()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private val _metricsFlow = MutableSharedFlow<Pair<String, PerfMetrics>>(extraBufferCapacity = 128)
    val metricsFlow: SharedFlow<Pair<String, PerfMetrics>> = _metricsFlow.asSharedFlow()

    fun startSession(
        packageName: String?,
        metrics: List<String>,
        intervalMs: Long = 1000
    ): String {
        val sessionId = UUID.randomUUID().toString()
        val runner = PerfSessionRunner(
            sessionId = sessionId,
            packageName = packageName,
            requestedMetrics = metrics,
            intervalMs = intervalMs
        )
        sessions[sessionId] = runner
        runner.start()
        return sessionId
    }

    fun stopSession(sessionId: String): PerfSessionResult? {
        val runner = sessions.remove(sessionId) ?: return null
        runner.stop()
        return runner.getResult()
    }

    fun getSnapshot(packageName: String?, metrics: List<String>): PerfMetrics {
        return collectOnce(packageName, metrics)
    }

    fun getSession(sessionId: String): PerfSessionRunner? = sessions[sessionId]

    fun stopAll() {
        sessions.values.forEach { it.stop() }
        sessions.clear()
        scope.cancel()
    }

    private fun collectOnce(packageName: String?, metrics: List<String>): PerfMetrics {
        return PerfMetrics(
            timestamp = System.currentTimeMillis(),
            cpu = if ("cpu" in metrics) cpuCollector.collect(packageName) else null,
            memory = if ("memory" in metrics) memoryCollector.collect(packageName) else null,
            fps = if ("fps" in metrics) fpsCollector.collect(packageName) else null,
            network = if ("network" in metrics) networkCollector.collect() else null,
            battery = if ("battery" in metrics) batteryCollector.collect() else null
        )
    }

    inner class PerfSessionRunner(
        val sessionId: String,
        val packageName: String?,
        val requestedMetrics: List<String>,
        val intervalMs: Long
    ) {
        private val dataPoints = mutableListOf<PerfMetrics>()
        private var job: Job? = null
        val startTime = System.currentTimeMillis()

        fun start() {
            job = scope.launch {
                while (isActive) {
                    val metrics = collectOnce(packageName, requestedMetrics)
                    synchronized(dataPoints) { dataPoints.add(metrics) }
                    _metricsFlow.emit(sessionId to metrics)
                    delay(intervalMs)
                }
            }
        }

        fun stop() {
            job?.cancel()
            job = null
        }

        fun getResult(): PerfSessionResult {
            val points = synchronized(dataPoints) { dataPoints.toList() }
            return PerfSessionResult(
                sessionId = sessionId,
                packageName = packageName,
                durationMs = System.currentTimeMillis() - startTime,
                dataPoints = points,
                summary = computeSummary(points)
            )
        }

        private fun computeSummary(points: List<PerfMetrics>): PerfSummary {
            val cpuValues = points.mapNotNull { it.cpu?.appUsage }
            val memValues = points.mapNotNull { it.memory?.totalPss }
            val fpsValues = points.mapNotNull { it.fps?.currentFps }
            val jankTotal = points.mapNotNull { it.fps?.jankCount }.sum()

            return PerfSummary(
                avgCpu = cpuValues.average().toFloat(),
                maxCpu = cpuValues.maxOrNull()?.toFloat() ?: 0f,
                minCpu = cpuValues.minOrNull()?.toFloat() ?: 0f,
                avgMemory = memValues.average().toLong(),
                maxMemory = memValues.maxOrNull() ?: 0,
                avgFps = fpsValues.average().toFloat(),
                minFps = fpsValues.minOrNull()?.toFloat() ?: 0f,
                jankCount = jankTotal,
                sampleCount = points.size
            )
        }
    }
}

data class PerfSessionResult(
    val sessionId: String,
    val packageName: String?,
    val durationMs: Long,
    val dataPoints: List<PerfMetrics>,
    val summary: PerfSummary
)

data class PerfSummary(
    val avgCpu: Float = 0f,
    val maxCpu: Float = 0f,
    val minCpu: Float = 0f,
    val avgMemory: Long = 0,
    val maxMemory: Long = 0,
    val avgFps: Float = 0f,
    val minFps: Float = 0f,
    val jankCount: Int = 0,
    val sampleCount: Int = 0
)
