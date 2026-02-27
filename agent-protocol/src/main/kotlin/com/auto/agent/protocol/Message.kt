package com.auto.agent.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import java.util.UUID

@Serializable
enum class MessageType {
    @SerialName("request") REQUEST,
    @SerialName("response") RESPONSE,
    @SerialName("event") EVENT,
    @SerialName("stream_start") STREAM_START,
    @SerialName("stream_data") STREAM_DATA,
    @SerialName("stream_end") STREAM_END,
    @SerialName("cancel") CANCEL
}

@Serializable
data class MessageError(
    val code: Int,
    val category: String,
    val message: String,
    val details: JsonObject? = null,
    val recoverable: Boolean = false,
    val suggestedAction: String? = null
)

@Serializable
data class MessageMetadata(
    val timeout: Long? = null,
    val retryCount: Int = 0,
    val priority: String = "normal",
    val traceId: String? = null
)

@Serializable
data class Message(
    val id: String = UUID.randomUUID().toString(),
    val type: MessageType,
    val method: String? = null,
    val params: JsonObject? = null,
    val result: JsonElement? = null,
    val error: MessageError? = null,
    val metadata: MessageMetadata? = null,
    val timestamp: Long = System.currentTimeMillis()
) {
    companion object {
        fun request(
            method: String,
            params: JsonObject? = null,
            metadata: MessageMetadata? = null
        ) = Message(
            type = MessageType.REQUEST,
            method = method,
            params = params,
            metadata = metadata
        )

        fun response(
            requestId: String,
            method: String,
            result: JsonElement? = null,
            error: MessageError? = null
        ) = Message(
            id = requestId,
            type = MessageType.RESPONSE,
            method = method,
            result = result,
            error = error
        )

        fun event(
            method: String,
            params: JsonObject? = null
        ) = Message(
            type = MessageType.EVENT,
            method = method,
            params = params
        )

        fun streamData(
            sessionId: String,
            method: String,
            params: JsonObject? = null
        ) = Message(
            id = sessionId,
            type = MessageType.STREAM_DATA,
            method = method,
            params = params
        )
    }
}
