package com.auto.agent.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.auto.agent.core.model.Selector
import com.auto.agent.core.model.UiElement
import kotlinx.coroutines.*
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine

/**
 * AccessibilityService providing non-Root UI automation capabilities.
 * Handles UI hierarchy dumping, element interaction, and gesture dispatch.
 */
class AgentAccessibilityService : AccessibilityService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.i(TAG, "AccessibilityService connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Events can be processed for toast detection, window changes, etc.
        event ?: return
        when (event.eventType) {
            AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED -> {
                // Toast / notification detection
                val text = event.text.joinToString()
                if (text.isNotEmpty()) {
                    lastToastText = text
                    lastToastTimestamp = System.currentTimeMillis()
                }
            }
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                currentPackage = event.packageName?.toString()
                currentActivity = event.className?.toString()
            }
            else -> {}
        }
    }

    override fun onInterrupt() {
        Log.w(TAG, "AccessibilityService interrupted")
    }

    override fun onDestroy() {
        instance = null
        scope.cancel()
        super.onDestroy()
    }

    // ---- UI Hierarchy ----

    fun dumpHierarchy(): List<UiElement> {
        val root = rootInActiveWindow ?: return emptyList()
        return listOf(nodeToElement(root, 0))
    }

    fun findElements(selector: Selector): List<UiElement> {
        val root = rootInActiveWindow ?: return emptyList()
        val results = mutableListOf<UiElement>()
        searchNode(root, selector, results, 0)
        return results
    }

    private fun searchNode(
        node: AccessibilityNodeInfo,
        selector: Selector,
        results: MutableList<UiElement>,
        depth: Int
    ) {
        val element = nodeToElement(node, depth)
        if (selector.matches(element)) {
            results.add(element)
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            searchNode(child, selector, results, depth + 1)
        }
    }

    private fun nodeToElement(node: AccessibilityNodeInfo, depth: Int): UiElement {
        val rect = Rect()
        node.getBoundsInScreen(rect)

        val children = mutableListOf<UiElement>()
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            children.add(nodeToElement(child, depth + 1))
        }

        return UiElement(
            id = "${node.hashCode()}",
            resourceId = node.viewIdResourceName,
            className = node.className?.toString() ?: "",
            packageName = node.packageName?.toString(),
            text = node.text?.toString(),
            contentDescription = node.contentDescription?.toString(),
            bounds = com.auto.agent.core.model.Rect(rect.left, rect.top, rect.right, rect.bottom),
            isClickable = node.isClickable,
            isEnabled = node.isEnabled,
            isFocusable = node.isFocusable,
            isFocused = node.isFocused,
            isScrollable = node.isScrollable,
            isCheckable = node.isCheckable,
            isChecked = node.isChecked,
            isSelected = node.isSelected,
            isVisibleToUser = node.isVisibleToUser,
            depth = depth,
            childCount = node.childCount,
            children = children
        )
    }

    // ---- Input Actions ----

    fun clickElement(node: AccessibilityNodeInfo): Boolean {
        return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    fun longClickElement(node: AccessibilityNodeInfo): Boolean {
        return node.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK)
    }

    fun setTextElement(node: AccessibilityNodeInfo, text: String): Boolean {
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    suspend fun performClick(x: Int, y: Int): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return false
        return performGesture(createClickGesture(x, y))
    }

    suspend fun performLongClick(x: Int, y: Int, durationMs: Long): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return false
        return performGesture(createLongClickGesture(x, y, durationMs))
    }

    suspend fun performSwipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Long): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return false
        return performGesture(createSwipeGesture(x1, y1, x2, y2, durationMs))
    }

    // ---- Global Actions ----

    fun pressBack(): Boolean = performGlobalAction(GLOBAL_ACTION_BACK)
    fun pressHome(): Boolean = performGlobalAction(GLOBAL_ACTION_HOME)
    fun pressRecents(): Boolean = performGlobalAction(GLOBAL_ACTION_RECENTS)
    fun openNotifications(): Boolean = performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
    fun openQuickSettings(): Boolean = performGlobalAction(GLOBAL_ACTION_QUICK_SETTINGS)

    // ---- Gesture Helpers ----

    private fun createClickGesture(x: Int, y: Int): GestureDescription {
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val stroke = GestureDescription.StrokeDescription(path, 0, 50)
        return GestureDescription.Builder().addStroke(stroke).build()
    }

    private fun createLongClickGesture(x: Int, y: Int, durationMs: Long): GestureDescription {
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs)
        return GestureDescription.Builder().addStroke(stroke).build()
    }

    private fun createSwipeGesture(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Long): GestureDescription {
        val path = Path().apply {
            moveTo(x1.toFloat(), y1.toFloat())
            lineTo(x2.toFloat(), y2.toFloat())
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs)
        return GestureDescription.Builder().addStroke(stroke).build()
    }

    private suspend fun performGesture(gesture: GestureDescription): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return false
        return suspendCoroutine { continuation ->
            val callback = object : GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) {
                    continuation.resume(true)
                }
                override fun onCancelled(gestureDescription: GestureDescription?) {
                    continuation.resume(false)
                }
            }
            dispatchGesture(gesture, callback, null)
        }
    }

    companion object {
        private const val TAG = "AgentA11yService"

        @Volatile
        var instance: AgentAccessibilityService? = null
            private set

        var lastToastText: String? = null
            private set
        var lastToastTimestamp: Long = 0
            private set
        var currentPackage: String? = null
            private set
        var currentActivity: String? = null
            private set
    }
}
