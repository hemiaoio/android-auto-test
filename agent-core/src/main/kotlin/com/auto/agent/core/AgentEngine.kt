package com.auto.agent.core

import android.content.Context
import com.auto.agent.core.handlers.*
import com.auto.agent.core.plugin.PluginManager
import com.auto.agent.protocol.Message
import com.auto.agent.protocol.Methods
import com.auto.agent.transport.TransportConfig
import com.auto.agent.transport.TransportServer
import kotlinx.coroutines.*
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject

/**
 * Central orchestrator that wires all subsystems and dispatches incoming messages.
 * This is the main entry point for the agent engine.
 */
class AgentEngine(
    private val context: Context,
    private val transport: TransportServer,
    private val commandRouter: CommandRouter,
    private val capabilityResolver: CapabilityResolver,
    private val pluginManager: PluginManager,
    private val shellExecutor: ShellExecutor? = null,
    private val toastProvider: ToastProvider? = null
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var isStarted = false

    suspend fun start(config: TransportConfig = TransportConfig()) {
        if (isStarted) return

        // Register built-in handlers
        registerSystemHandlers()
        registerCoreHandlers()

        // Load plugins
        pluginManager.loadPlugins()

        // Start transport
        transport.onMessage { request -> commandRouter.route(request) }
        transport.start(config)

        isStarted = true
    }

    suspend fun stop() {
        if (!isStarted) return

        pluginManager.unloadAll()
        transport.stop()
        scope.cancel()
        isStarted = false
    }

    fun registerHandler(handler: CommandHandler) {
        commandRouter.register(handler)
    }

    suspend fun emitEvent(event: Message) {
        transport.sendEvent(event)
    }

    /**
     * Register all core command handlers (App, Device, UI).
     */
    private fun registerCoreHandlers() {
        val shell = shellExecutor ?: DefaultShellExecutor()

        // App handlers
        commandRouter.register(AppLaunchHandler(context, shell))
        commandRouter.register(AppStopHandler(shell))
        commandRouter.register(AppClearHandler(shell))
        commandRouter.register(AppInstallHandler(shell))
        commandRouter.register(AppUninstallHandler(shell))
        commandRouter.register(AppListHandler(shell))
        commandRouter.register(AppInfoHandler(context, shell))
        commandRouter.register(AppPermissionsHandler(shell))

        // Device handlers
        commandRouter.register(DeviceInfoHandler(context, capabilityResolver))
        commandRouter.register(ScreenshotHandler(capabilityResolver, shell))
        commandRouter.register(ShellHandler(shell))
        commandRouter.register(InputKeyHandler(capabilityResolver, shell))
        commandRouter.register(WakeHandler(context, shell))
        commandRouter.register(RebootHandler(shell))
        commandRouter.register(RotationHandler(shell))
        commandRouter.register(ClipboardHandler(context))

        // UI handlers
        commandRouter.register(UiClickHandler(capabilityResolver, shell))
        commandRouter.register(UiLongClickHandler(capabilityResolver, shell))
        commandRouter.register(UiDoubleClickHandler(capabilityResolver, shell))
        commandRouter.register(UiTypeHandler(capabilityResolver, shell))
        commandRouter.register(UiSwipeHandler(capabilityResolver, shell))
        commandRouter.register(UiScrollHandler(capabilityResolver, shell))
        commandRouter.register(UiFindHandler(capabilityResolver))
        commandRouter.register(UiDumpHandler(capabilityResolver, shell))
        commandRouter.register(UiWaitForHandler(capabilityResolver))
        commandRouter.register(UiToastHandler(toastProvider))
        commandRouter.register(UiGestureHandler(capabilityResolver, shell))
        commandRouter.register(UiPinchHandler(shell))
    }

    private fun registerSystemHandlers() {
        // system.capabilities handler
        commandRouter.register(object : CommandHandler {
            override val method = Methods.System.CAPABILITIES
            override suspend fun handle(
                params: kotlinx.serialization.json.JsonObject?,
                context: RequestContext
            ): kotlinx.serialization.json.JsonElement {
                val caps = capabilityResolver.getCapabilities()
                return buildJsonObject {
                    put("root", JsonPrimitive(caps.root))
                    put("accessibility", JsonPrimitive(caps.accessibility))
                    put("apiLevel", JsonPrimitive(caps.apiLevel))
                    put("inputStrategy", JsonPrimitive(caps.inputStrategy))
                    put("captureStrategy", JsonPrimitive(caps.captureStrategy))
                    put("hierarchyStrategy", JsonPrimitive(caps.hierarchyStrategy))
                    put("registeredMethods", kotlinx.serialization.json.JsonArray(
                        commandRouter.registeredMethods.sorted().map { JsonPrimitive(it) }
                    ))
                }
            }
        })

        // system.heartbeat handler
        commandRouter.register(object : CommandHandler {
            override val method = Methods.System.HEARTBEAT
            override suspend fun handle(
                params: kotlinx.serialization.json.JsonObject?,
                context: RequestContext
            ): kotlinx.serialization.json.JsonElement {
                val runtime = Runtime.getRuntime()
                return buildJsonObject {
                    put("uptime", JsonPrimitive(android.os.SystemClock.elapsedRealtime()))
                    put("freeMemory", JsonPrimitive(runtime.freeMemory()))
                    put("totalMemory", JsonPrimitive(runtime.totalMemory()))
                    put("timestamp", JsonPrimitive(System.currentTimeMillis()))
                }
            }
        })
    }
}

/**
 * Default ShellExecutor using non-root shell.
 */
class DefaultShellExecutor : ShellExecutor {
    override suspend fun execute(command: String, timeoutMs: Long): com.auto.agent.core.model.ShellResult {
        return kotlinx.coroutines.withContext(Dispatchers.IO) {
            try {
                val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", command))
                val stdout = process.inputStream.bufferedReader().readText()
                val stderr = process.errorStream.bufferedReader().readText()
                val exitCode = process.waitFor()
                com.auto.agent.core.model.ShellResult(exitCode, stdout.trim(), stderr.trim())
            } catch (e: Exception) {
                com.auto.agent.core.model.ShellResult(-1, "", e.message ?: "Unknown error")
            }
        }
    }

    override suspend fun executeAsRoot(command: String, timeoutMs: Long): com.auto.agent.core.model.ShellResult {
        return kotlinx.coroutines.withContext(Dispatchers.IO) {
            try {
                val process = Runtime.getRuntime().exec(arrayOf("su", "-c", command))
                val stdout = process.inputStream.bufferedReader().readText()
                val stderr = process.errorStream.bufferedReader().readText()
                val exitCode = process.waitFor()
                com.auto.agent.core.model.ShellResult(exitCode, stdout.trim(), stderr.trim())
            } catch (e: Exception) {
                com.auto.agent.core.model.ShellResult(-1, "", e.message ?: "Unknown error")
            }
        }
    }
}
