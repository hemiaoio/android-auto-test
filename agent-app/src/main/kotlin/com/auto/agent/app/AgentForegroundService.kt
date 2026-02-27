package com.auto.agent.app

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.auto.agent.core.AgentEngine
import com.auto.agent.core.CapabilityResolver
import com.auto.agent.core.CommandRouter
import com.auto.agent.core.plugin.PluginManager
import com.auto.agent.transport.TransportConfig
import com.auto.agent.transport.WebSocketTransportServer
import kotlinx.coroutines.*

/**
 * Foreground service that keeps the Agent engine running.
 */
class AgentForegroundService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var engine: AgentEngine? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIFICATION_ID, createNotification("Starting..."))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startAgent()
            ACTION_STOP -> stopAgent()
        }
        return START_STICKY
    }

    private fun startAgent() {
        if (engine != null) return

        scope.launch {
            try {
                val transport = WebSocketTransportServer()
                val commandRouter = CommandRouter()
                val capabilityResolver = CapabilityResolver()

                // Detect capabilities
                val isRooted = checkRoot()
                val isAccessibilityEnabled = checkAccessibility()
                capabilityResolver.updateCapabilities(
                    root = isRooted,
                    accessibility = isAccessibilityEnabled,
                    api = android.os.Build.VERSION.SDK_INT
                )

                val pluginContext = AgentPluginContext(this@AgentForegroundService, capabilityResolver)
                val pluginManager = PluginManager(this@AgentForegroundService, commandRouter, pluginContext)

                engine = AgentEngine(
                    context = this@AgentForegroundService,
                    transport = transport,
                    commandRouter = commandRouter,
                    capabilityResolver = capabilityResolver,
                    pluginManager = pluginManager
                )

                val config = TransportConfig()
                engine?.start(config)

                updateNotification("Running on port ${config.controlPort}")
                broadcastStatus(true)
            } catch (e: Exception) {
                updateNotification("Error: ${e.message}")
                broadcastStatus(false)
            }
        }
    }

    private fun stopAgent() {
        scope.launch {
            engine?.stop()
            engine = null
            broadcastStatus(false)
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
    }

    private fun checkRoot(): Boolean {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("su", "-c", "id"))
            val result = process.inputStream.bufferedReader().readText()
            process.waitFor()
            result.contains("uid=0")
        } catch (_: Exception) {
            false
        }
    }

    private fun checkAccessibility(): Boolean {
        val enabledServices = android.provider.Settings.Secure.getString(
            contentResolver,
            android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        return enabledServices.contains("com.auto.agent/com.auto.agent.accessibility.AgentAccessibilityService")
    }

    private fun createNotification(status: String): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, AgentApplication.CHANNEL_ID)
            .setContentTitle("AutoTest Agent")
            .setContentText(status)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(status: String) {
        val notification = createNotification(status)
        val manager = getSystemService(NOTIFICATION_SERVICE) as android.app.NotificationManager
        manager.notify(NOTIFICATION_ID, notification)
    }

    private fun broadcastStatus(running: Boolean) {
        val intent = Intent(ACTION_STATUS_CHANGED).apply {
            putExtra(EXTRA_IS_RUNNING, running)
        }
        sendBroadcast(intent)
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        const val ACTION_START = "com.auto.agent.START"
        const val ACTION_STOP = "com.auto.agent.STOP"
        const val ACTION_STATUS_CHANGED = "com.auto.agent.STATUS_CHANGED"
        const val EXTRA_IS_RUNNING = "is_running"
        private const val NOTIFICATION_ID = 1001

        fun start(context: Context) {
            val intent = Intent(context, AgentForegroundService::class.java).apply {
                action = ACTION_START
            }
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            val intent = Intent(context, AgentForegroundService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }
    }
}

/**
 * Plugin context implementation for the agent service.
 */
private class AgentPluginContext(
    private val context: Context,
    private val capabilityResolver: CapabilityResolver
) : com.auto.agent.core.plugin.PluginContext {
    override val agentVersion: String = "1.0.0"
    override val isRooted: Boolean get() = capabilityResolver.getCapabilities().root
    override val isAccessibilityEnabled: Boolean get() = capabilityResolver.getCapabilities().accessibility
    override val apiLevel: Int get() = android.os.Build.VERSION.SDK_INT
    override val dataDir: String get() = context.filesDir.absolutePath

    override suspend fun executeShell(command: String): String {
        val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", command))
        val result = process.inputStream.bufferedReader().readText()
        process.waitFor()
        return result
    }

    override suspend fun emitEvent(type: String, data: Map<String, Any?>) {
        // Events are routed through the engine's transport
    }
}
