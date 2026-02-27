package com.auto.agent.protocol

object Events {

    // Connection lifecycle events
    const val CONNECTED = "event.connected"
    const val DISCONNECTED = "event.disconnected"
    const val RECONNECTING = "event.reconnecting"

    // Device state events
    const val SCREEN_STATE_CHANGED = "event.device.screenState"
    const val ROTATION_CHANGED = "event.device.rotation"
    const val BATTERY_LOW = "event.device.batteryLow"

    // App lifecycle events
    const val APP_CRASHED = "event.app.crashed"
    const val APP_ANR = "event.app.anr"
    const val APP_STARTED = "event.app.started"
    const val APP_STOPPED = "event.app.stopped"

    // UI events
    const val TOAST_SHOWN = "event.ui.toast"
    const val DIALOG_SHOWN = "event.ui.dialog"
    const val NOTIFICATION_POSTED = "event.ui.notification"
    const val WINDOW_CHANGED = "event.ui.windowChanged"

    // Performance events
    const val PERF_THRESHOLD_EXCEEDED = "event.perf.threshold"
    const val PERF_DATA = "event.perf.data"

    // Log events
    const val LOG_ENTRY = "event.log.entry"
    const val LOG_CRASH = "event.log.crash"

    // Task events
    const val TASK_STARTED = "event.task.started"
    const val TASK_PROGRESS = "event.task.progress"
    const val TASK_COMPLETED = "event.task.completed"
    const val TASK_FAILED = "event.task.failed"

    // Plugin events
    const val PLUGIN_LOADED = "event.plugin.loaded"
    const val PLUGIN_UNLOADED = "event.plugin.unloaded"
    const val PLUGIN_ERROR = "event.plugin.error"
}
