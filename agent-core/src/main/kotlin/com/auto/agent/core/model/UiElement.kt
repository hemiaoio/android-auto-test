package com.auto.agent.core.model

import kotlinx.serialization.Serializable

@Serializable
data class UiElement(
    val id: String,
    val resourceId: String? = null,
    val className: String,
    val packageName: String? = null,
    val text: String? = null,
    val contentDescription: String? = null,
    val bounds: Rect,
    val isClickable: Boolean = false,
    val isEnabled: Boolean = true,
    val isFocusable: Boolean = false,
    val isFocused: Boolean = false,
    val isScrollable: Boolean = false,
    val isCheckable: Boolean = false,
    val isChecked: Boolean = false,
    val isSelected: Boolean = false,
    val isVisibleToUser: Boolean = true,
    val depth: Int = 0,
    val childCount: Int = 0,
    val children: List<UiElement> = emptyList()
) {
    val centerX: Int get() = (bounds.left + bounds.right) / 2
    val centerY: Int get() = (bounds.top + bounds.bottom) / 2
}

@Serializable
data class Rect(
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int
) {
    val width: Int get() = right - left
    val height: Int get() = bottom - top
    val centerX: Int get() = (left + right) / 2
    val centerY: Int get() = (top + bottom) / 2

    fun contains(x: Int, y: Int): Boolean =
        x in left..right && y in top..bottom
}
