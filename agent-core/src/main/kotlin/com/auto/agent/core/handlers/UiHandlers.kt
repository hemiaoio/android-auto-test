package com.auto.agent.core.handlers

import com.auto.agent.core.*
import com.auto.agent.core.model.Selector
import com.auto.agent.core.model.UiElement
import com.auto.agent.protocol.Methods
import kotlinx.coroutines.delay
import kotlinx.serialization.json.*

/**
 * ui.click — Click at coordinates or by selector.
 */
class UiClickHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Ui.CLICK

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val x = params?.get("x")?.jsonPrimitive?.intOrNull
        val y = params?.get("y")?.jsonPrimitive?.intOrNull

        if (x != null && y != null) {
            // Coordinate click
            val inputStrategy = capabilityResolver.resolveInputStrategy()
            if (inputStrategy != null) {
                val result = inputStrategy.click(x, y)
                return buildJsonObject { put("success", JsonPrimitive(result.isSuccess)) }
            }
            // Fallback to shell
            val result = shell.execute("input tap $x $y")
            return buildJsonObject { put("success", JsonPrimitive(result.exitCode == 0)) }
        }

        // Selector-based click: find element, then click its center
        val selector = parseSelectorFromParams(params)
        val hierarchyStrategy = capabilityResolver.resolveHierarchyStrategy()
            ?: throw AgentException(4001, "No hierarchy strategy available")

        val elements = hierarchyStrategy.findElements(selector).getOrElse { emptyList() }
        if (elements.isEmpty()) {
            return buildJsonObject {
                put("success", JsonPrimitive(false))
                put("error", JsonPrimitive("Element not found"))
            }
        }

        val target = elements.first()
        val cx = target.centerX
        val cy = target.centerY

        val inputStrategy = capabilityResolver.resolveInputStrategy()
        if (inputStrategy != null) {
            val result = inputStrategy.click(cx, cy)
            return buildJsonObject {
                put("success", JsonPrimitive(result.isSuccess))
                put("x", JsonPrimitive(cx))
                put("y", JsonPrimitive(cy))
            }
        }

        val result = shell.execute("input tap $cx $cy")
        return buildJsonObject {
            put("success", JsonPrimitive(result.exitCode == 0))
            put("x", JsonPrimitive(cx))
            put("y", JsonPrimitive(cy))
        }
    }
}

/**
 * ui.longClick — Long press at coordinates or by selector.
 */
class UiLongClickHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Ui.LONG_CLICK

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val x = params?.get("x")?.jsonPrimitive?.intOrNull
        val y = params?.get("y")?.jsonPrimitive?.intOrNull
        val durationMs = params?.get("duration")?.jsonPrimitive?.longOrNull ?: 500L

        val (cx, cy) = resolveCoordinates(x, y, params, capabilityResolver)

        val inputStrategy = capabilityResolver.resolveInputStrategy()
        if (inputStrategy != null) {
            val result = inputStrategy.longClick(cx, cy, durationMs)
            return buildJsonObject { put("success", JsonPrimitive(result.isSuccess)) }
        }

        val result = shell.execute("input swipe $cx $cy $cx $cy $durationMs")
        return buildJsonObject { put("success", JsonPrimitive(result.exitCode == 0)) }
    }
}

/**
 * ui.doubleClick — Double click at coordinates.
 */
class UiDoubleClickHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Ui.DOUBLE_CLICK

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val x = params?.get("x")?.jsonPrimitive?.intOrNull
        val y = params?.get("y")?.jsonPrimitive?.intOrNull
        val (cx, cy) = resolveCoordinates(x, y, params, capabilityResolver)

        val inputStrategy = capabilityResolver.resolveInputStrategy()
        if (inputStrategy != null) {
            inputStrategy.click(cx, cy)
            delay(100)
            val result = inputStrategy.click(cx, cy)
            return buildJsonObject { put("success", JsonPrimitive(result.isSuccess)) }
        }

        shell.execute("input tap $cx $cy")
        delay(100)
        val result = shell.execute("input tap $cx $cy")
        return buildJsonObject { put("success", JsonPrimitive(result.exitCode == 0)) }
    }
}

/**
 * ui.type — Input text.
 */
class UiTypeHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Ui.TYPE

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val text = params?.get("text")?.jsonPrimitive?.content
            ?: throw IllegalArgumentException("text is required")

        val inputStrategy = capabilityResolver.resolveInputStrategy()
        if (inputStrategy != null) {
            val result = inputStrategy.type(text)
            return buildJsonObject { put("success", JsonPrimitive(result.isSuccess)) }
        }

        // Fallback: escape and use shell input
        val escaped = text.replace(" ", "%s")
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
        val result = shell.execute("input text \"$escaped\"")
        return buildJsonObject { put("success", JsonPrimitive(result.exitCode == 0)) }
    }
}

/**
 * ui.swipe — Perform swipe gesture.
 */
class UiSwipeHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Ui.SWIPE

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val x1 = params?.get("x1")?.jsonPrimitive?.intOrNull
            ?: params?.get("startX")?.jsonPrimitive?.intOrNull
            ?: throw IllegalArgumentException("x1/startX is required")
        val y1 = params?.get("y1")?.jsonPrimitive?.intOrNull
            ?: params?.get("startY")?.jsonPrimitive?.intOrNull
            ?: throw IllegalArgumentException("y1/startY is required")
        val x2 = params?.get("x2")?.jsonPrimitive?.intOrNull
            ?: params?.get("endX")?.jsonPrimitive?.intOrNull
            ?: throw IllegalArgumentException("x2/endX is required")
        val y2 = params?.get("y2")?.jsonPrimitive?.intOrNull
            ?: params?.get("endY")?.jsonPrimitive?.intOrNull
            ?: throw IllegalArgumentException("y2/endY is required")
        val durationMs = params?.get("duration")?.jsonPrimitive?.longOrNull ?: 300L

        val inputStrategy = capabilityResolver.resolveInputStrategy()
        if (inputStrategy != null) {
            val result = inputStrategy.swipe(x1, y1, x2, y2, durationMs)
            return buildJsonObject { put("success", JsonPrimitive(result.isSuccess)) }
        }

        val result = shell.execute("input swipe $x1 $y1 $x2 $y2 $durationMs")
        return buildJsonObject { put("success", JsonPrimitive(result.exitCode == 0)) }
    }
}

/**
 * ui.scroll — Scroll in a direction.
 */
class UiScrollHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Ui.SCROLL

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val direction = params?.get("direction")?.jsonPrimitive?.content ?: "down"
        val distance = params?.get("distance")?.jsonPrimitive?.intOrNull ?: 500
        val cx = params?.get("x")?.jsonPrimitive?.intOrNull ?: 540
        val cy = params?.get("y")?.jsonPrimitive?.intOrNull ?: 960

        val (x2, y2) = when (direction) {
            "up" -> cx to (cy - distance)
            "down" -> cx to (cy + distance)
            "left" -> (cx - distance) to cy
            "right" -> (cx + distance) to cy
            else -> cx to (cy + distance)
        }

        val inputStrategy = capabilityResolver.resolveInputStrategy()
        if (inputStrategy != null) {
            val result = inputStrategy.swipe(cx, cy, x2, y2, 300)
            return buildJsonObject { put("success", JsonPrimitive(result.isSuccess)) }
        }

        val result = shell.execute("input swipe $cx $cy $x2 $y2 300")
        return buildJsonObject { put("success", JsonPrimitive(result.exitCode == 0)) }
    }
}

/**
 * ui.find — Find UI elements by selector.
 */
class UiFindHandler(
    private val capabilityResolver: CapabilityResolver
) : CommandHandler {
    override val method = Methods.Ui.FIND

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val selector = parseSelectorFromParams(params)

        val hierarchyStrategy = capabilityResolver.resolveHierarchyStrategy()
            ?: throw AgentException(4001, "No hierarchy strategy available")

        val elements = hierarchyStrategy.findElements(selector).getOrElse { emptyList() }

        return buildJsonObject {
            put("elements", JsonArray(elements.map { it.toJson() }))
            put("count", JsonPrimitive(elements.size))
        }
    }
}

/**
 * ui.dump — Dump the full UI hierarchy.
 */
class UiDumpHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Ui.DUMP

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val hierarchyStrategy = capabilityResolver.resolveHierarchyStrategy()

        if (hierarchyStrategy != null) {
            val elements = hierarchyStrategy.dump().getOrElse { emptyList() }
            return buildJsonObject {
                put("elements", JsonArray(elements.map { it.toJson() }))
                put("count", JsonPrimitive(elements.size))
            }
        }

        // Fallback to uiautomator dump
        shell.execute("uiautomator dump /data/local/tmp/uidump.xml")
        val result = shell.execute("cat /data/local/tmp/uidump.xml")
        shell.execute("rm -f /data/local/tmp/uidump.xml")

        return buildJsonObject {
            put("hierarchy", JsonPrimitive(result.stdout))
            put("format", JsonPrimitive("xml"))
        }
    }
}

/**
 * ui.waitFor — Wait for an element to appear or disappear.
 */
class UiWaitForHandler(
    private val capabilityResolver: CapabilityResolver
) : CommandHandler {
    override val method = Methods.Ui.WAIT_FOR

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val selector = parseSelectorFromParams(params)
        val timeoutMs = params?.get("timeout")?.jsonPrimitive?.longOrNull ?: 10_000
        val condition = params?.get("condition")?.jsonPrimitive?.contentOrNull ?: "exists"
        val pollMs = params?.get("pollInterval")?.jsonPrimitive?.longOrNull ?: 500

        val hierarchyStrategy = capabilityResolver.resolveHierarchyStrategy()
            ?: throw AgentException(4001, "No hierarchy strategy available")

        val deadline = System.currentTimeMillis() + timeoutMs

        while (System.currentTimeMillis() < deadline) {
            val elements = hierarchyStrategy.findElements(selector).getOrElse { emptyList() }
            val found = elements.isNotEmpty()

            when (condition) {
                "exists" -> if (found) {
                    val el = elements.first()
                    return buildJsonObject {
                        put("found", JsonPrimitive(true))
                        put("element", el.toJson())
                    }
                }
                "gone" -> if (!found) {
                    return buildJsonObject { put("found", JsonPrimitive(false)) }
                }
            }

            delay(pollMs)
        }

        // Timeout
        return buildJsonObject {
            put("found", JsonPrimitive(condition == "gone"))
            put("timedOut", JsonPrimitive(true))
        }
    }
}

/**
 * Provider interface for toast text, to avoid circular dependency with agent-accessibility.
 */
interface ToastProvider {
    val lastToastText: String?
    val lastToastTimestamp: Long
}

/**
 * ui.toast — Get the last detected toast text.
 */
class UiToastHandler(
    private val toastProvider: ToastProvider? = null
) : CommandHandler {
    override val method = Methods.Ui.TOAST

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        return buildJsonObject {
            put("text", JsonPrimitive(toastProvider?.lastToastText ?: ""))
            put("timestamp", JsonPrimitive(toastProvider?.lastToastTimestamp ?: 0L))
        }
    }
}

/**
 * ui.gesture — Perform a custom gesture (path of points).
 */
class UiGestureHandler(
    private val capabilityResolver: CapabilityResolver,
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Ui.GESTURE

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val points = params?.get("points")?.jsonArray
            ?: throw IllegalArgumentException("points array is required")
        val durationMs = params["duration"]?.jsonPrimitive?.longOrNull ?: 300L

        if (points.size < 2) throw IllegalArgumentException("At least 2 points required")

        val first = points[0].jsonObject
        val last = points[points.size - 1].jsonObject

        val x1 = first["x"]?.jsonPrimitive?.intOrNull ?: 0
        val y1 = first["y"]?.jsonPrimitive?.intOrNull ?: 0
        val x2 = last["x"]?.jsonPrimitive?.intOrNull ?: 0
        val y2 = last["y"]?.jsonPrimitive?.intOrNull ?: 0

        val inputStrategy = capabilityResolver.resolveInputStrategy()
        if (inputStrategy != null) {
            val result = inputStrategy.swipe(x1, y1, x2, y2, durationMs)
            return buildJsonObject { put("success", JsonPrimitive(result.isSuccess)) }
        }

        val result = shell.execute("input swipe $x1 $y1 $x2 $y2 $durationMs")
        return buildJsonObject { put("success", JsonPrimitive(result.exitCode == 0)) }
    }
}

/**
 * ui.pinch — Pinch in/out gesture (zoom).
 */
class UiPinchHandler(
    private val shell: ShellExecutor
) : CommandHandler {
    override val method = Methods.Ui.PINCH

    override suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement {
        val cx = params?.get("x")?.jsonPrimitive?.intOrNull ?: 540
        val cy = params?.get("y")?.jsonPrimitive?.intOrNull ?: 960
        val direction = params?.get("direction")?.jsonPrimitive?.contentOrNull ?: "in"  // "in" or "out"
        val distance = params?.get("distance")?.jsonPrimitive?.intOrNull ?: 200

        // Simulate pinch with two sequential swipes
        if (direction == "out") {
            shell.execute("input swipe $cx $cy ${cx - distance} ${cy - distance} 300")
            shell.execute("input swipe $cx $cy ${cx + distance} ${cy + distance} 300")
        } else {
            shell.execute("input swipe ${cx - distance} ${cy - distance} $cx $cy 300")
            shell.execute("input swipe ${cx + distance} ${cy + distance} $cx $cy 300")
        }

        return buildJsonObject {
            put("success", JsonPrimitive(true))
            put("direction", JsonPrimitive(direction))
        }
    }
}

// ---- Helper functions ----

internal fun parseSelectorFromParams(params: JsonObject?): Selector {
    val sel = params?.get("selector")?.jsonObject ?: params ?: JsonObject(emptyMap())
    return Selector(
        resourceId = sel["resourceId"]?.jsonPrimitive?.contentOrNull,
        text = sel["text"]?.jsonPrimitive?.contentOrNull,
        textContains = sel["textContains"]?.jsonPrimitive?.contentOrNull,
        textMatches = sel["textMatches"]?.jsonPrimitive?.contentOrNull,
        className = sel["className"]?.jsonPrimitive?.contentOrNull,
        description = sel["description"]?.jsonPrimitive?.contentOrNull
            ?: sel["contentDesc"]?.jsonPrimitive?.contentOrNull,
        descriptionContains = sel["descriptionContains"]?.jsonPrimitive?.contentOrNull,
        packageName = sel["packageName"]?.jsonPrimitive?.contentOrNull,
        index = sel["index"]?.jsonPrimitive?.intOrNull,
        enabled = sel["enabled"]?.jsonPrimitive?.booleanOrNull,
        clickable = sel["clickable"]?.jsonPrimitive?.booleanOrNull,
        scrollable = sel["scrollable"]?.jsonPrimitive?.booleanOrNull,
    )
}

internal suspend fun resolveCoordinates(
    x: Int?, y: Int?, params: JsonObject?, capabilityResolver: CapabilityResolver
): Pair<Int, Int> {
    if (x != null && y != null) return x to y

    val selector = parseSelectorFromParams(params)
    val hierarchyStrategy = capabilityResolver.resolveHierarchyStrategy()
        ?: throw AgentException(4001, "No hierarchy strategy available")

    val elements = hierarchyStrategy.findElements(selector).getOrElse { emptyList() }
    if (elements.isEmpty()) {
        throw AgentException(4002, "Element not found for selector")
    }

    val target = elements.first()
    return target.centerX to target.centerY
}

internal fun UiElement.toJson(): JsonObject = buildJsonObject {
    put("id", JsonPrimitive(id))
    resourceId?.let { put("resourceId", JsonPrimitive(it)) }
    put("className", JsonPrimitive(className))
    packageName?.let { put("packageName", JsonPrimitive(it)) }
    text?.let { put("text", JsonPrimitive(it)) }
    contentDescription?.let { put("contentDescription", JsonPrimitive(it)) }
    put("bounds", buildJsonObject {
        put("left", JsonPrimitive(bounds.left))
        put("top", JsonPrimitive(bounds.top))
        put("right", JsonPrimitive(bounds.right))
        put("bottom", JsonPrimitive(bounds.bottom))
    })
    put("isClickable", JsonPrimitive(isClickable))
    put("isEnabled", JsonPrimitive(isEnabled))
    put("isScrollable", JsonPrimitive(isScrollable))
    put("isChecked", JsonPrimitive(isChecked))
    put("isSelected", JsonPrimitive(isSelected))
    put("depth", JsonPrimitive(depth))
    put("childCount", JsonPrimitive(childCount))
}
