package com.auto.agent.root

import com.auto.agent.core.InputStrategy
import com.auto.agent.core.ShellExecutor

/**
 * Root-based input strategy using `input` shell commands.
 * Faster and more reliable than AccessibilityService for input injection.
 */
class RootInputStrategy(
    private val shell: ShellExecutor
) : InputStrategy {

    override val name: String = "root"
    override val requiresRoot: Boolean = true

    override suspend fun click(x: Int, y: Int): Result<Unit> {
        val result = shell.executeAsRoot("input tap $x $y")
        return if (result.exitCode == 0) Result.success(Unit)
        else Result.failure(RuntimeException("Click failed: ${result.stderr}"))
    }

    override suspend fun longClick(x: Int, y: Int, durationMs: Long): Result<Unit> {
        val result = shell.executeAsRoot("input swipe $x $y $x $y $durationMs")
        return if (result.exitCode == 0) Result.success(Unit)
        else Result.failure(RuntimeException("Long click failed: ${result.stderr}"))
    }

    override suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Long): Result<Unit> {
        val result = shell.executeAsRoot("input swipe $x1 $y1 $x2 $y2 $durationMs")
        return if (result.exitCode == 0) Result.success(Unit)
        else Result.failure(RuntimeException("Swipe failed: ${result.stderr}"))
    }

    override suspend fun type(text: String): Result<Unit> {
        // Escape special characters for shell
        val escaped = text.replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace(" ", "%s")
            .replace("'", "\\'")
        val result = shell.executeAsRoot("input text \"$escaped\"")
        return if (result.exitCode == 0) Result.success(Unit)
        else Result.failure(RuntimeException("Type failed: ${result.stderr}"))
    }

    override suspend fun keyEvent(keyCode: Int): Result<Unit> {
        val result = shell.executeAsRoot("input keyevent $keyCode")
        return if (result.exitCode == 0) Result.success(Unit)
        else Result.failure(RuntimeException("Key event failed: ${result.stderr}"))
    }
}
