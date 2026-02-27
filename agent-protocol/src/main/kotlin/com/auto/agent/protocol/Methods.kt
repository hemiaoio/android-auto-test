package com.auto.agent.protocol

object Methods {

    // Device info & control
    object Device {
        const val INFO = "device.info"
        const val SCREENSHOT = "device.screenshot"
        const val SHELL = "device.shell"
        const val INPUT_KEY = "device.inputKey"
        const val REBOOT = "device.reboot"
        const val ROTATION = "device.rotation"
        const val WAKE = "device.wake"
        const val CLIPBOARD = "device.clipboard"
    }

    // UI operations
    object Ui {
        const val FIND = "ui.find"
        const val CLICK = "ui.click"
        const val LONG_CLICK = "ui.longClick"
        const val DOUBLE_CLICK = "ui.doubleClick"
        const val TYPE = "ui.type"
        const val SWIPE = "ui.swipe"
        const val SCROLL = "ui.scroll"
        const val DUMP = "ui.dump"
        const val WAIT_FOR = "ui.waitFor"
        const val TOAST = "ui.toast"
        const val GESTURE = "ui.gesture"
        const val PINCH = "ui.pinch"
    }

    // Performance monitoring
    object Perf {
        const val START = "perf.start"
        const val STOP = "perf.stop"
        const val SNAPSHOT = "perf.snapshot"
        const val STREAM = "perf.stream"
    }

    // App management
    object App {
        const val LAUNCH = "app.launch"
        const val STOP = "app.stop"
        const val CLEAR = "app.clear"
        const val INSTALL = "app.install"
        const val UNINSTALL = "app.uninstall"
        const val LIST = "app.list"
        const val INFO = "app.info"
        const val PERMISSIONS = "app.permissions"
    }

    // Log management
    object Log {
        const val START = "log.start"
        const val STOP = "log.stop"
        const val FILTER = "log.filter"
        const val DUMP = "log.dump"
    }

    // File operations
    object File {
        const val PUSH = "file.push"
        const val PULL = "file.pull"
        const val LIST = "file.list"
        const val DELETE = "file.delete"
        const val STAT = "file.stat"
        const val MKDIR = "file.mkdir"
    }

    // Task management
    object Task {
        const val EXECUTE = "task.execute"
        const val CANCEL = "task.cancel"
        const val STATUS = "task.status"
        const val LIST = "task.list"
    }

    // System internal
    object System {
        const val HEARTBEAT = "system.heartbeat"
        const val CAPABILITIES = "system.capabilities"
        const val CONFIGURE = "system.configure"
        const val SHUTDOWN = "system.shutdown"
    }
}
