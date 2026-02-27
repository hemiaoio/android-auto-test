package com.auto.agent.protocol

object ErrorCodes {

    // 1000-1999: Transport / Connection
    object Transport {
        const val AUTH_FAILED = 1001
        const val SESSION_EXPIRED = 1002
        const val RATE_LIMITED = 1003
        const val CONNECTION_LOST = 1004
        const val PROTOCOL_ERROR = 1005
        const val TIMEOUT = 1006
    }

    // 2000-2999: Device / System
    object Device {
        const val OFFLINE = 2001
        const val LOW_MEMORY = 2002
        const val PERMISSION_DENIED = 2003
        const val ROOT_REQUIRED = 2004
        const val ACCESSIBILITY_REQUIRED = 2005
        const val UNSUPPORTED_API_LEVEL = 2006
        const val SCREEN_OFF = 2007
    }

    // 3000-3999: App Management
    object App {
        const val NOT_INSTALLED = 3001
        const val CRASHED = 3002
        const val INSTALL_FAILED = 3003
        const val UNINSTALL_FAILED = 3004
        const val NOT_RUNNING = 3005
        const val LAUNCH_TIMEOUT = 3006
    }

    // 4000-4999: UI Operations
    object Ui {
        const val ELEMENT_NOT_FOUND = 4001
        const val ELEMENT_NOT_VISIBLE = 4002
        const val ELEMENT_NOT_CLICKABLE = 4003
        const val STALE_ELEMENT = 4004
        const val GESTURE_FAILED = 4005
        const val HIERARCHY_UNAVAILABLE = 4006
        const val TYPE_FAILED = 4007
    }

    // 5000-5999: Performance / Monitoring
    object Perf {
        const val ALREADY_RUNNING = 5001
        const val INSUFFICIENT_STORAGE = 5002
        const val COLLECTOR_NOT_FOUND = 5003
        const val SESSION_NOT_FOUND = 5004
    }

    // 6000-6999: File Operations
    object File {
        const val NOT_FOUND = 6001
        const val ACCESS_DENIED = 6002
        const val STORAGE_FULL = 6003
        const val TRANSFER_FAILED = 6004
    }

    // 7000-7999: Plugin Errors
    object Plugin {
        const val NOT_FOUND = 7001
        const val INIT_FAILED = 7002
        const val EXECUTION_TIMEOUT = 7003
        const val DEPENDENCY_MISSING = 7004
    }

    // 9000-9999: Internal
    object Internal {
        const val ERROR = 9001
        const val NOT_IMPLEMENTED = 9002
        const val UNKNOWN = 9999
    }

    fun categoryOf(code: Int): String = when (code) {
        in 1000..1999 -> "TRANSPORT"
        in 2000..2999 -> "DEVICE"
        in 3000..3999 -> "APP"
        in 4000..4999 -> "UI"
        in 5000..5999 -> "PERFORMANCE"
        in 6000..6999 -> "FILE"
        in 7000..7999 -> "PLUGIN"
        in 9000..9999 -> "INTERNAL"
        else -> "UNKNOWN"
    }

    fun isRecoverable(code: Int): Boolean = when (code) {
        Transport.RATE_LIMITED,
        Transport.TIMEOUT,
        Device.LOW_MEMORY,
        Device.SCREEN_OFF,
        Ui.ELEMENT_NOT_FOUND,
        Ui.ELEMENT_NOT_VISIBLE,
        Ui.STALE_ELEMENT,
        App.LAUNCH_TIMEOUT -> true
        else -> false
    }
}
