package com.auto.agent.root

import java.io.File

/**
 * Detects whether the device is rooted via multiple heuristics.
 */
object RootChecker {

    fun isRooted(): Boolean {
        return checkSuBinary() || checkSuCommand() || checkMagisk()
    }

    private fun checkSuBinary(): Boolean {
        val paths = arrayOf(
            "/system/bin/su",
            "/system/xbin/su",
            "/sbin/su",
            "/system/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/data/local/su"
        )
        return paths.any { File(it).exists() }
    }

    private fun checkSuCommand(): Boolean {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("su", "-c", "id"))
            val result = process.inputStream.bufferedReader().readText()
            process.waitFor()
            process.exitValue() == 0 && result.contains("uid=0")
        } catch (_: Exception) {
            false
        }
    }

    private fun checkMagisk(): Boolean {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("magisk", "-v"))
            process.waitFor()
            process.exitValue() == 0
        } catch (_: Exception) {
            false
        }
    }
}
