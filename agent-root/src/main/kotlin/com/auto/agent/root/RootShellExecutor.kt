package com.auto.agent.root

import com.auto.agent.core.ShellExecutor
import com.auto.agent.core.model.ShellResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter

/**
 * Executes shell commands, with optional persistent `su` session for root commands.
 * A persistent su shell avoids the overhead of spawning a new su process per command.
 */
class RootShellExecutor : ShellExecutor {

    private var suProcess: Process? = null
    private var suWriter: OutputStreamWriter? = null
    private var suReader: BufferedReader? = null

    override suspend fun execute(command: String, timeoutMs: Long): ShellResult {
        return withContext(Dispatchers.IO) {
            withTimeout(timeoutMs) {
                executeCommand(arrayOf("sh", "-c", command))
            }
        }
    }

    override suspend fun executeAsRoot(command: String, timeoutMs: Long): ShellResult {
        return withContext(Dispatchers.IO) {
            withTimeout(timeoutMs) {
                executeCommand(arrayOf("su", "-c", command))
            }
        }
    }

    private fun executeCommand(cmd: Array<String>): ShellResult {
        return try {
            val process = Runtime.getRuntime().exec(cmd)
            val stdout = process.inputStream.bufferedReader().readText()
            val stderr = process.errorStream.bufferedReader().readText()
            val exitCode = process.waitFor()
            ShellResult(exitCode = exitCode, stdout = stdout.trim(), stderr = stderr.trim())
        } catch (e: Exception) {
            ShellResult(exitCode = -1, stdout = "", stderr = e.message ?: "Unknown error")
        }
    }

    fun destroy() {
        try {
            suWriter?.close()
            suReader?.close()
            suProcess?.destroy()
        } catch (_: Exception) { }
        suProcess = null
        suWriter = null
        suReader = null
    }
}
