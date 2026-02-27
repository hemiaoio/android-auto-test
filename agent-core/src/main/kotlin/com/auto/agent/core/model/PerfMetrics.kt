package com.auto.agent.core.model

import kotlinx.serialization.Serializable

@Serializable
data class PerfMetrics(
    val timestamp: Long = System.currentTimeMillis(),
    val cpu: CpuMetrics? = null,
    val memory: MemoryMetrics? = null,
    val fps: FpsMetrics? = null,
    val network: NetworkMetrics? = null,
    val battery: BatteryMetrics? = null
)

@Serializable
data class CpuMetrics(
    val totalUsage: Float,
    val appUsage: Float,
    val coreCount: Int,
    val perCoreUsage: List<Float> = emptyList()
)

@Serializable
data class MemoryMetrics(
    val totalPss: Long,
    val nativePss: Long,
    val dalvikPss: Long,
    val totalRam: Long,
    val availableRam: Long,
    val javaHeap: Long,
    val javaHeapMax: Long
)

@Serializable
data class FpsMetrics(
    val currentFps: Float,
    val avgFps: Float,
    val jankCount: Int,
    val bigJankCount: Int,
    val frameTimes: List<Long> = emptyList()
)

@Serializable
data class NetworkMetrics(
    val rxBytes: Long,
    val txBytes: Long,
    val rxSpeed: Long,
    val txSpeed: Long
)

@Serializable
data class BatteryMetrics(
    val level: Int,
    val temperature: Float,
    val voltage: Int,
    val isCharging: Boolean,
    val currentNow: Long
)

@Serializable
data class PerfSession(
    val sessionId: String,
    val packageName: String?,
    val metrics: List<String>,
    val intervalMs: Long,
    val startTime: Long = System.currentTimeMillis(),
    val dataPoints: MutableList<PerfMetrics> = mutableListOf()
)
