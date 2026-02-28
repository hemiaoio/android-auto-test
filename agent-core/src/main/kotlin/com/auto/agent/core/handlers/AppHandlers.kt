package com.auto.agent.core.handlers

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.SystemClock
import com.auto.agent.core.CommandHandler
import com.auto.agent.core.RequestContext
import com.auto.agent.core.ShellExecutor
import com.auto.agent.protocol.Methods
import kotlinx.coroutines.delay
import kotlinx.serialization.json.*

/**
 * app.launch — Launch an application by package name.
 */
class AppLaunchHandler(
    private val context: Context,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.App.LAUNCH

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val packageName = params?.get("packageName")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("packageName is required")
        val activity = params["activity"]?.jsonPrimitive?.contentOrNull
        val clearState = params["clearState"]?.jsonPrimitive?.booleanOrNull ?: false
        val waitForIdle = params["waitForIdle"]?.jsonPrimitive?.booleanOrNull ?: true

        if (clearState) {
            shell.execute("pm clear $packageName")
        }

        val startTime = SystemClock.elapsedRealtime()

        if (activity != null) {
            shell.execute("am start -n $packageName/$activity")
        } else {
            // Use monkey to launch the default activity
            shell.execute("monkey -p $packageName -c android.intent.category.LAUNCHER 1")
        }

        if (waitForIdle) {
            delay(1000) // Wait for app to settle
        }

        val launchTimeMs = SystemClock.elapsedRealtime() - startTime

        return buildJsonObject {
            put("launchTimeMs", JsonPrimitive(launchTimeMs))
            put("packageName", JsonPrimitive(packageName))
        }
    }
}

/**
 * app.stop — Force-stop an application.
 */
class AppStopHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.App.STOP

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val packageName = params?.get("packageName")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("packageName is required")

        val result = shell.execute("am force-stop $packageName")

        return buildJsonObject {
            put("success", JsonPrimitive(result.exitCode == 0))
        }
    }
}

/**
 * app.clear — Clear application data.
 */
class AppClearHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.App.CLEAR

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val packageName = params?.get("packageName")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("packageName is required")

        val result = shell.execute("pm clear $packageName")

        return buildJsonObject {
            put("success", JsonPrimitive(result.exitCode == 0))
            put("output", JsonPrimitive(result.stdout))
        }
    }
}

/**
 * app.install — Install an APK from device path.
 */
class AppInstallHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.App.INSTALL

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val path = params?.get("path")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("path is required")
        val replace = params["replace"]?.jsonPrimitive?.booleanOrNull ?: true
        val grantPermissions = params["grantPermissions"]?.jsonPrimitive?.booleanOrNull ?: true

        val flags = buildString {
            if (replace) append("-r ")
            if (grantPermissions) append("-g ")
        }.trim()

        val result = shell.execute("pm install $flags \"$path\"")

        return buildJsonObject {
            put("success", JsonPrimitive(result.exitCode == 0))
            put("output", JsonPrimitive(result.stdout))
        }
    }
}

/**
 * app.uninstall — Uninstall an application.
 */
class AppUninstallHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.App.UNINSTALL

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val packageName = params?.get("packageName")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("packageName is required")

        val result = shell.execute("pm uninstall $packageName")

        return buildJsonObject {
            put("success", JsonPrimitive(result.exitCode == 0))
            put("output", JsonPrimitive(result.stdout))
        }
    }
}

/**
 * app.list — List installed packages.
 */
class AppListHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.App.LIST

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val filter = params?.get("filter")?.jsonPrimitive?.contentOrNull

        val cmd = if (filter != null) "pm list packages $filter" else "pm list packages"
        val result = shell.execute(cmd)

        val packages = result.stdout.lines()
            .filter { it.startsWith("package:") }
            .map { it.removePrefix("package:").trim() }

        return buildJsonObject {
            put("packages", JsonArray(packages.map { JsonPrimitive(it) }))
            put("count", JsonPrimitive(packages.size))
        }
    }
}

/**
 * app.info — Get information about an installed application.
 */
class AppInfoHandler(
    private val appContext: Context,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.App.INFO

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val packageName = params?.get("packageName")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("packageName is required")

        // Check if running
        val psResult = shell.execute("pidof $packageName")
        val isRunning = psResult.stdout.isNotBlank()

        // Get package info
        val pm = appContext.packageManager
        return try {
            val info = pm.getPackageInfo(packageName, 0)
            buildJsonObject {
                put("packageName", JsonPrimitive(packageName))
                put("versionName", JsonPrimitive(info.versionName ?: ""))
                put("versionCode", JsonPrimitive(info.longVersionCode))
                put("isRunning", JsonPrimitive(isRunning))
                put("firstInstall", JsonPrimitive(info.firstInstallTime))
                put("lastUpdate", JsonPrimitive(info.lastUpdateTime))
            }
        } catch (e: PackageManager.NameNotFoundException) {
            buildJsonObject {
                put("packageName", JsonPrimitive(packageName))
                put("installed", JsonPrimitive(false))
            }
        }
    }
}

/**
 * app.permissions — Query or grant permissions.
 */
class AppPermissionsHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.App.PERMISSIONS

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val packageName = params?.get("packageName")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("packageName is required")
        val grant = params["grant"]?.jsonPrimitive?.contentOrNull
        val revoke = params["revoke"]?.jsonPrimitive?.contentOrNull

        if (grant != null) {
            shell.execute("pm grant $packageName $grant")
            return buildJsonObject { put("granted", JsonPrimitive(grant)) }
        }

        if (revoke != null) {
            shell.execute("pm revoke $packageName $revoke")
            return buildJsonObject { put("revoked", JsonPrimitive(revoke)) }
        }

        // List permissions
        val result = shell.execute("dumpsys package $packageName | grep permission")
        return buildJsonObject {
            put("permissions", JsonPrimitive(result.stdout))
        }
    }
}
