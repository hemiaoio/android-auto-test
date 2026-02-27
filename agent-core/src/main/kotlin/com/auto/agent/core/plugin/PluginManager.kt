package com.auto.agent.core.plugin

import android.content.Context
import com.auto.agent.core.CommandRouter
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.File

/**
 * Manages plugin lifecycle: discovery, loading, starting, stopping, unloading.
 * Plugins are loaded from DEX/APK files in the plugins directory.
 */
class PluginManager(
    private val context: Context,
    private val commandRouter: CommandRouter,
    private val pluginContext: PluginContext
) {
    private val plugins = mutableMapOf<String, PluginEntry>()
    private val mutex = Mutex()

    private data class PluginEntry(
        val plugin: AutoTestPlugin,
        val classLoader: ClassLoader?,
        var state: PluginState = PluginState.LOADED
    )

    enum class PluginState {
        LOADED, INITIALIZED, STARTED, STOPPED, ERROR
    }

    val pluginDir: File
        get() = File(context.filesDir, "plugins").also { it.mkdirs() }

    suspend fun loadPlugins() {
        mutex.withLock {
            val dir = pluginDir
            if (!dir.exists()) return

            dir.listFiles()?.filter { it.extension in listOf("apk", "dex", "jar") }?.forEach { file ->
                try {
                    loadPlugin(file)
                } catch (e: Exception) {
                    android.util.Log.e(TAG, "Failed to load plugin from ${file.name}", e)
                }
            }
        }
    }

    suspend fun loadPlugin(file: File): AutoTestPlugin? {
        val classLoader = dalvik.system.DexClassLoader(
            file.absolutePath,
            context.codeCacheDir.absolutePath,
            null,
            context.classLoader
        )

        // Try to load manifest from META-INF/plugin.properties
        val manifestStream = classLoader.getResourceAsStream("META-INF/plugin.properties")
        if (manifestStream == null) {
            android.util.Log.w(TAG, "No plugin manifest found in ${file.name}")
            return null
        }

        val props = java.util.Properties().apply { load(manifestStream) }
        val entryClass = props.getProperty("entry_class") ?: return null

        val pluginClass = classLoader.loadClass(entryClass)
        val plugin = pluginClass.getDeclaredConstructor().newInstance() as AutoTestPlugin

        plugin.onInit(pluginContext)

        // Register plugin handlers
        plugin.handlers.forEach { handler ->
            commandRouter.register(handler)
        }

        plugins[plugin.id] = PluginEntry(plugin, classLoader, PluginState.INITIALIZED)
        plugin.onStart()
        plugins[plugin.id]?.state = PluginState.STARTED

        android.util.Log.i(TAG, "Plugin loaded: ${plugin.displayName} v${plugin.version}")
        return plugin
    }

    suspend fun unloadPlugin(pluginId: String) {
        mutex.withLock {
            val entry = plugins[pluginId] ?: return
            try {
                entry.plugin.onStop()
                entry.plugin.onDestroy()
                entry.plugin.handlers.forEach { handler ->
                    commandRouter.unregister(handler.method)
                }
                plugins.remove(pluginId)
            } catch (e: Exception) {
                android.util.Log.e(TAG, "Failed to unload plugin $pluginId", e)
            }
        }
    }

    suspend fun unloadAll() {
        mutex.withLock {
            plugins.keys.toList().forEach { id ->
                try {
                    val entry = plugins[id]!!
                    entry.plugin.onStop()
                    entry.plugin.onDestroy()
                } catch (e: Exception) {
                    android.util.Log.e(TAG, "Error unloading plugin $id", e)
                }
            }
            plugins.clear()
        }
    }

    fun getLoadedPlugins(): List<AutoTestPlugin> = plugins.values.map { it.plugin }

    fun getPluginState(pluginId: String): PluginState? = plugins[pluginId]?.state

    companion object {
        private const val TAG = "PluginManager"
    }
}
