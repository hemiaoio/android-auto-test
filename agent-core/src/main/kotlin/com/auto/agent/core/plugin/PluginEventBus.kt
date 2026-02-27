package com.auto.agent.core.plugin

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Event bus for inter-plugin and plugin-to-agent communication.
 */
class PluginEventBus {

    private val _events = MutableSharedFlow<PluginEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<PluginEvent> = _events.asSharedFlow()

    private val listeners = mutableMapOf<String, MutableList<suspend (PluginEvent) -> Unit>>()

    suspend fun emit(event: PluginEvent) {
        _events.emit(event)
        listeners[event.type]?.forEach { listener ->
            try {
                listener(event)
            } catch (_: Exception) { }
        }
        // Wildcard listeners
        listeners["*"]?.forEach { listener ->
            try {
                listener(event)
            } catch (_: Exception) { }
        }
    }

    fun on(eventType: String, listener: suspend (PluginEvent) -> Unit): () -> Unit {
        val list = listeners.getOrPut(eventType) { mutableListOf() }
        list.add(listener)
        return { list.remove(listener) }
    }

    fun removeAllListeners(eventType: String? = null) {
        if (eventType != null) {
            listeners.remove(eventType)
        } else {
            listeners.clear()
        }
    }
}

data class PluginEvent(
    val type: String,
    val source: String,
    val data: Map<String, Any?> = emptyMap(),
    val timestamp: Long = System.currentTimeMillis()
)
