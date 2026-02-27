package com.auto.agent.core

import com.auto.agent.core.model.*

/**
 * Unified device operation interface.
 * Abstracts Root vs non-Root into a single API surface.
 */
interface DeviceController {

    suspend fun getDeviceInfo(): DeviceInfo

    // Input operations
    suspend fun click(x: Int, y: Int): Result<Unit>
    suspend fun longClick(x: Int, y: Int, durationMs: Long = 500): Result<Unit>
    suspend fun doubleClick(x: Int, y: Int): Result<Unit>
    suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Long = 300): Result<Unit>
    suspend fun type(text: String): Result<Unit>
    suspend fun keyEvent(keyCode: Int): Result<Unit>

    // UI hierarchy
    suspend fun dumpHierarchy(): Result<List<UiElement>>
    suspend fun findElements(selector: Selector): Result<List<UiElement>>

    // Screenshot
    suspend fun takeScreenshot(config: ScreenshotConfig = ScreenshotConfig()): Result<ByteArray>

    // Shell
    suspend fun executeShell(command: String, asRoot: Boolean = false): Result<ShellResult>

    // App management
    suspend fun launchApp(packageName: String, activity: String? = null, clearState: Boolean = false): Result<Long>
    suspend fun stopApp(packageName: String, force: Boolean = true): Result<Unit>
    suspend fun clearAppData(packageName: String): Result<Unit>
    suspend fun installApp(path: String, replace: Boolean = true, grantPermissions: Boolean = true): Result<String>
    suspend fun uninstallApp(packageName: String): Result<Unit>
}

/**
 * Strategy interfaces for capability-based dispatch.
 */
interface InputStrategy {
    val name: String
    val requiresRoot: Boolean
    suspend fun click(x: Int, y: Int): Result<Unit>
    suspend fun longClick(x: Int, y: Int, durationMs: Long): Result<Unit>
    suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Long): Result<Unit>
    suspend fun type(text: String): Result<Unit>
    suspend fun keyEvent(keyCode: Int): Result<Unit>
}

interface ScreenCaptureStrategy {
    val name: String
    val requiresRoot: Boolean
    suspend fun capture(config: ScreenshotConfig): Result<ByteArray>
}

interface HierarchyStrategy {
    val name: String
    suspend fun dump(): Result<List<UiElement>>
    suspend fun findElements(selector: Selector): Result<List<UiElement>>
}

interface ShellExecutor {
    suspend fun execute(command: String, timeoutMs: Long = 30_000): ShellResult
    suspend fun executeAsRoot(command: String, timeoutMs: Long = 30_000): ShellResult
}
