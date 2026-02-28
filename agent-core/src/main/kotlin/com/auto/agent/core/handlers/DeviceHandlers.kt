package com.auto.agent.core.handlers

import android.content.Context
import android.os.Build
import android.os.PowerManager
import android.util.Base64
import android.util.DisplayMetrics
import android.view.WindowManager
import com.auto.agent.core.*
import com.auto.agent.core.model.ScreenshotConfig
import com.auto.agent.core.model.ImageFormat
import com.auto.agent.protocol.Methods
import kotlinx.serialization.json.*

/**
 * device.info — Return device information.
 */
class DeviceInfoHandler(
    private val context: Context,
    private val capabilityResolver: CapabilityResolver
) : CommandHandler {
    override val method = Methods.Device.INFO

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val wm = this.context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val dm = DisplayMetrics()
        @Suppress("DEPRECATION")
        wm.defaultDisplay.getRealMetrics(dm)

        val caps = capabilityResolver.getCapabilities()

        return buildJsonObject {
            put("model", JsonPrimitive(Build.MODEL))
            put("manufacturer", JsonPrimitive(Build.MANUFACTURER))
            put("brand", JsonPrimitive(Build.BRAND))
            put("sdkVersion", JsonPrimitive(Build.VERSION.SDK_INT))
            put("androidVersion", JsonPrimitive(Build.VERSION.RELEASE))
            put("abi", JsonPrimitive(Build.SUPPORTED_ABIS.firstOrNull() ?: "unknown"))
            put("screenWidth", JsonPrimitive(dm.widthPixels))
            put("screenHeight", JsonPrimitive(dm.heightPixels))
            put("density", JsonPrimitive(dm.density))
            put("isRooted", JsonPrimitive(caps.root))
            put("isAccessibilityEnabled", JsonPrimitive(caps.accessibility))
            put("serial", JsonPrimitive(Build.SERIAL ?: "unknown"))
            put("buildFingerprint", JsonPrimitive(Build.FINGERPRINT))
        }
    }
}

/**
 * device.screenshot — Capture the screen and return base64-encoded PNG.
 */
class ScreenshotHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Device.SCREENSHOT

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val quality = params?.get("quality")?.jsonPrimitive?.intOrNull ?: 100
        val scale = params?.get("scale")?.jsonPrimitive?.floatOrNull ?: 1.0f

        val captureStrategy = capabilityResolver.resolveCaptureStrategy()
        if (captureStrategy != null) {
            val config = ScreenshotConfig(
                format = ImageFormat.PNG,
                quality = quality,
                scale = scale
            )
            val result = captureStrategy.capture(config)
            val bytes = result.getOrElse {
                // Fallback to shell screencap
                return captureViaShell()
            }
            val base64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
            return buildJsonObject {
                put("data", JsonPrimitive(base64))
                put("format", JsonPrimitive("png"))
            }
        }

        // Fallback: use shell screencap
        return captureViaShell()
    }

    private suspend fun captureViaShell(): JsonElement {
        val tmpFile = "/data/local/tmp/autotest_screenshot.png"
        shell.execute("screencap -p $tmpFile")
        val catResult = shell.execute("cat $tmpFile | base64")
        shell.execute("rm -f $tmpFile")

        // If base64 not available via shell, read raw and encode
        if (catResult.stdout.isBlank()) {
            // Try direct read
            val rawResult = shell.execute("screencap -p")
            val base64 = Base64.encodeToString(rawResult.stdout.toByteArray(), Base64.NO_WRAP)
            return buildJsonObject {
                put("data", JsonPrimitive(base64))
                put("format", JsonPrimitive("png"))
            }
        }

        return buildJsonObject {
            put("data", JsonPrimitive(catResult.stdout.replace("\n", "")))
            put("format", JsonPrimitive("png"))
        }
    }
}

/**
 * device.shell — Execute a shell command.
 */
class ShellHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Device.SHELL

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val command = params?.get("command")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("command is required")
        val asRoot = params["asRoot"]?.jsonPrimitive?.booleanOrNull ?: false
        val timeoutMs = params["timeout"]?.jsonPrimitive?.longOrNull ?: 30_000

        val result = if (asRoot) {
            shell.executeAsRoot(command, timeoutMs)
        } else {
            shell.execute(command, timeoutMs)
        }

        return buildJsonObject {
            put("exitCode", JsonPrimitive(result.exitCode))
            put("stdout", JsonPrimitive(result.stdout))
            put("stderr", JsonPrimitive(result.stderr))
        }
    }
}

/**
 * device.inputKey — Send a key event.
 */
class InputKeyHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Device.INPUT_KEY

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val keyCode = params?.get("keyCode")?.jsonPrimitive?.intOrNull
            ?: throw IllegalArgumentException("keyCode is required")

        val inputStrategy = capabilityResolver.resolveInputStrategy()
        if (inputStrategy != null) {
            val result = inputStrategy.keyEvent(keyCode)
            return buildJsonObject {
                put("success", JsonPrimitive(result.isSuccess))
            }
        }

        // Fallback to shell
        val result = shell.execute("input keyevent $keyCode")
        return buildJsonObject {
            put("success", JsonPrimitive(result.exitCode == 0))
        }
    }
}

/**
 * device.wake — Wake up the screen.
 */
class WakeHandler(
    private val context: Context,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Device.WAKE

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val pm = this.context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val isScreenOn = pm.isInteractive

        if (!isScreenOn) {
            shell.execute("input keyevent KEYCODE_WAKEUP")
        }

        return buildJsonObject {
            put("wasAsleep", JsonPrimitive(!isScreenOn))
            put("success", JsonPrimitive(true))
        }
    }
}

/**
 * device.reboot — Reboot the device.
 */
class RebootHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Device.REBOOT

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val mode = params?.get("mode")?.jsonPrimitive?.contentOrNull // "recovery", "bootloader", null

        val cmd = when (mode) {
            "recovery" -> "reboot recovery"
            "bootloader" -> "reboot bootloader"
            else -> "reboot"
        }

        shell.execute(cmd)
        return buildJsonObject {
            put("success", JsonPrimitive(true))
        }
    }
}

/**
 * device.rotation — Get or set screen rotation.
 */
class RotationHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Device.ROTATION

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val setRotation = params?.get("rotation")?.jsonPrimitive?.intOrNull

        if (setRotation != null) {
            // Disable auto-rotate and set rotation
            shell.execute("settings put system accelerometer_rotation 0")
            shell.execute("settings put system user_rotation $setRotation")
            return buildJsonObject {
                put("rotation", JsonPrimitive(setRotation))
                put("success", JsonPrimitive(true))
            }
        }

        // Get current rotation
        val result = shell.execute("settings get system user_rotation")
        val rotation = result.stdout.trim().toIntOrNull() ?: 0

        return buildJsonObject {
            put("rotation", JsonPrimitive(rotation))
        }
    }
}

/**
 * device.clipboard — Read or write clipboard content.
 */
class ClipboardHandler(
    private val context: Context
) : CommandHandler {
    override val method = Methods.Device.CLIPBOARD

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val setText = params?.get("text")?.jsonPrimitive?.contentOrNull
        val cm = this.context.getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager

        if (setText != null) {
            val clip = android.content.ClipData.newPlainText("autotest", setText)
            cm.setPrimaryClip(clip)
            return buildJsonObject {
                put("success", JsonPrimitive(true))
            }
        }

        // Read clipboard
        val clip = cm.primaryClip
        val text = if (clip != null && clip.itemCount > 0) {
            clip.getItemAt(0).text?.toString() ?: ""
        } else ""

        return buildJsonObject {
            put("text", JsonPrimitive(text))
        }
    }
}
