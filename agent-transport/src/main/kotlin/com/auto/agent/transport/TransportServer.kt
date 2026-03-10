package com.auto.agent.transport

import com.auto.agent.protocol.Message

interface TransportServer {

    val isRunning: Boolean

    suspend fun start(config: TransportConfig)

    suspend fun stop()

    fun onMessage(handler: suspend (Message) -> Message?)

    fun onBinaryMessage(handler: suspend (BinaryFrame) -> BinaryFrame?)

    suspend fun sendEvent(message: Message)

    suspend fun sendBinary(frame: BinaryFrame)

    suspend fun broadcast(message: Message)
}

/** 传输模式：正向（设备当服务器）或 反向（设备连接 PC 服务器）。 */
enum class TransportMode {
    SERVER,
    CLIENT
}

data class TransportConfig(
    // 正向模式端口
    val controlPort: Int = 18900,
    val binaryPort: Int = 18901,
    val eventPort: Int = 18902,
    val host: String = "0.0.0.0",
    val authToken: String? = null,
    val maxConnections: Int = 5,
    val heartbeatIntervalMs: Long = 5_000,
    val heartbeatTimeoutMs: Long = 15_000,
    // 传输模式
    val mode: TransportMode = TransportMode.SERVER,
    // 反向模式配置
    val serverUrl: String = "",
    val deviceId: String = "",
    val reconnectBaseDelayMs: Long = 1_000,
    val reconnectMaxDelayMs: Long = 60_000,
    val reconnectMaxAttempts: Int = Int.MAX_VALUE
)

data class BinaryFrame(
    val messageId: String,
    val payloadType: PayloadType,
    val data: ByteArray,
    val compressed: Boolean = false,
    val chunked: Boolean = false,
    val finalChunk: Boolean = true
) {
    enum class PayloadType(val code: Byte) {
        SCREENSHOT_PNG(0x01),
        SCREENSHOT_JPEG(0x02),
        VIDEO_H264(0x03),
        FILE_DATA(0x04),
        HIERARCHY_XML(0x05)
    }

    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is BinaryFrame) return false
        return messageId == other.messageId && payloadType == other.payloadType && data.contentEquals(other.data)
    }

    override fun hashCode(): Int {
        var result = messageId.hashCode()
        result = 31 * result + payloadType.hashCode()
        result = 31 * result + data.contentHashCode()
        return result
    }
}
