package com.auto.agent.core

import kotlinx.serialization.Serializable

/**
 * Detects device capabilities and resolves the best strategy for each operation.
 * Root > Accessibility > Shell fallback
 */
class CapabilityResolver {

    private var rootAvailable: Boolean = false
    private var accessibilityAvailable: Boolean = false
    private var apiLevel: Int = 0

    private var inputStrategies: List<InputStrategy> = emptyList()
    private var captureStrategies: List<ScreenCaptureStrategy> = emptyList()
    private var hierarchyStrategies: List<HierarchyStrategy> = emptyList()

    fun registerInputStrategy(strategy: InputStrategy) {
        inputStrategies = inputStrategies + strategy
    }

    fun registerCaptureStrategy(strategy: ScreenCaptureStrategy) {
        captureStrategies = captureStrategies + strategy
    }

    fun registerHierarchyStrategy(strategy: HierarchyStrategy) {
        hierarchyStrategies = hierarchyStrategies + strategy
    }

    fun updateCapabilities(root: Boolean, accessibility: Boolean, api: Int) {
        rootAvailable = root
        accessibilityAvailable = accessibility
        apiLevel = api
    }

    /**
     * Resolve best input strategy: prefer root, then accessibility, then shell fallback
     */
    fun resolveInputStrategy(): InputStrategy? {
        if (rootAvailable) {
            inputStrategies.firstOrNull { it.requiresRoot }?.let { return it }
        }
        if (accessibilityAvailable) {
            inputStrategies.firstOrNull { !it.requiresRoot && it.name == "accessibility" }?.let { return it }
        }
        return inputStrategies.firstOrNull { !it.requiresRoot }
    }

    /**
     * Resolve best screenshot strategy: prefer root (no dialog), then MediaProjection
     */
    fun resolveCaptureStrategy(): ScreenCaptureStrategy? {
        if (rootAvailable) {
            captureStrategies.firstOrNull { it.requiresRoot }?.let { return it }
        }
        return captureStrategies.firstOrNull { !it.requiresRoot }
    }

    /**
     * Resolve hierarchy strategy: prefer accessibility (live, fast), then shell dump
     */
    fun resolveHierarchyStrategy(): HierarchyStrategy? {
        if (accessibilityAvailable) {
            hierarchyStrategies.firstOrNull { it.name == "accessibility" }?.let { return it }
        }
        return hierarchyStrategies.firstOrNull()
    }

    fun getCapabilities(): DeviceCapabilities = DeviceCapabilities(
        root = rootAvailable,
        accessibility = accessibilityAvailable,
        apiLevel = apiLevel,
        inputStrategy = resolveInputStrategy()?.name ?: "none",
        captureStrategy = resolveCaptureStrategy()?.name ?: "none",
        hierarchyStrategy = resolveHierarchyStrategy()?.name ?: "none"
    )
}

@Serializable
data class DeviceCapabilities(
    val root: Boolean,
    val accessibility: Boolean,
    val apiLevel: Int,
    val inputStrategy: String,
    val captureStrategy: String,
    val hierarchyStrategy: String,
    val plugins: List<String> = emptyList()
)
