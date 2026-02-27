package com.auto.agent.core.model

import kotlinx.serialization.Serializable

@Serializable
data class Selector(
    val resourceId: String? = null,
    val text: String? = null,
    val textContains: String? = null,
    val textMatches: String? = null,
    val className: String? = null,
    val description: String? = null,
    val descriptionContains: String? = null,
    val packageName: String? = null,
    val index: Int? = null,
    val instance: Int? = null,
    val enabled: Boolean? = null,
    val clickable: Boolean? = null,
    val scrollable: Boolean? = null,
    val focusable: Boolean? = null,
    val checked: Boolean? = null,
    val selected: Boolean? = null,
    val xpath: String? = null,
    val depth: Int? = null,
    val childSelector: Selector? = null,
    val parentSelector: Selector? = null
) {
    fun isEmpty(): Boolean = resourceId == null && text == null && textContains == null &&
            textMatches == null && className == null && description == null &&
            descriptionContains == null && packageName == null && xpath == null

    fun matches(element: UiElement): Boolean {
        if (resourceId != null && element.resourceId != resourceId) return false
        if (text != null && element.text != text) return false
        if (textContains != null && element.text?.contains(textContains) != true) return false
        if (textMatches != null && element.text?.matches(Regex(textMatches)) != true) return false
        if (className != null && element.className != className) return false
        if (description != null && element.contentDescription != description) return false
        if (descriptionContains != null && element.contentDescription?.contains(descriptionContains) != true) return false
        if (packageName != null && element.packageName != packageName) return false
        if (enabled != null && element.isEnabled != enabled) return false
        if (clickable != null && element.isClickable != clickable) return false
        if (scrollable != null && element.isScrollable != scrollable) return false
        return true
    }
}
