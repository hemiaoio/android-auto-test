package com.auto.agent.core

import android.content.Context
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
    private val pluginManager: PluginManager
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var isStarted = false

    suspend fun start(config: TransportConfig = TransportConfig()) {
        if (isStarted) return

        // Register built-in handlers
        registerSystemHandlers()

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
