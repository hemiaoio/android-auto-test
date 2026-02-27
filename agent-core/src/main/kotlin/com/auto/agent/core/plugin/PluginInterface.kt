package com.auto.agent.core.plugin

import com.auto.agent.core.CommandHandler

/**
 * Core plugin contract. Plugins extend the agent with new capabilities.
 * Plugins are loaded as separate DEX/APK files via DexClassLoader.
 */
interface AutoTestPlugin {
    val id: String
    val version: String
    val displayName: String
    val description: String

    /** Command handlers this plugin provides */
    val handlers: List<CommandHandler>

    /** Required capabilities (e.g., "root", "accessibility") */
    val requiredCapabilities: Set<String> get() = emptySet()

    /** Plugin dependencies by ID */
    val dependencies: Set<String> get() = emptySet()

    /** Called when plugin is loaded */
    suspend fun onInit(context: PluginContext)

    /** Called when plugin is started */
    suspend fun onStart()

    /** Called when plugin is stopped */
    suspend fun onStop()

    /** Called when plugin is unloaded */
    suspend fun onDestroy()
}

/**
 * Context provided to plugins for accessing agent capabilities.
 */
interface PluginContext {
    val agentVersion: String
    val isRooted: Boolean
    val isAccessibilityEnabled: Boolean
    val apiLevel: Int
    val dataDir: String

    suspend fun executeShell(command: String): String
    suspend fun emitEvent(type: String, data: Map<String, Any?>)
}

/**
 * Plugin metadata loaded from manifest.
 */
data class PluginManifest(
    val id: String,
    val version: String,
    val displayName: String,
    val entryClass: String,
    val minAgentVersion: String = "1.0.0",
    val requiredCapabilities: Set<String> = emptySet(),
    val dependencies: Set<String> = emptySet()
)
