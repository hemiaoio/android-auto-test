package com.auto.agent.transport

import com.auto.agent.protocol.Message
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

class MessageCodec {

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        prettyPrint = false
        isLenient = true
    }

    fun encode(message: Message): String {
        return json.encodeToString(message)
    }

    fun decode(text: String): Message {
        return json.decodeFromString<Message>(text)
    }

    fun encodeBinaryHeader(frame: BinaryFrame): ByteArray {
        val header = ByteArray(25) // 2 magic + 1 flags + 16 uuid + 2 type + 4 length
        // Magic: 0xA7 (AutoTest)
        header[0] = 0xA7.toByte()
        header[1] = 0x00

        // Flags
        var flags = 0
        if (frame.compressed) flags = flags or 0x01
        if (frame.chunked) flags = flags or 0x02
        if (frame.finalChunk) flags = flags or 0x04
        header[2] = flags.toByte()

        // Message ID (first 16 bytes of UUID string hash)
        val idBytes = frame.messageId.toByteArray(Charsets.UTF_8)
        val idHash = idBytes.copyOf(16)
        System.arraycopy(idHash, 0, header, 3, minOf(idHash.size, 16))

        // Payload type (2 bytes)
        header[19] = 0x00
        header[20] = frame.payloadType.code

        // Payload length (4 bytes, big-endian)
        val length = frame.data.size
        header[21] = (length shr 24 and 0xFF).toByte()
        header[22] = (length shr 16 and 0xFF).toByte()
        header[23] = (length shr 8 and 0xFF).toByte()
        header[24] = (length and 0xFF).toByte()

        return header
    }

    fun encodeBinaryFrame(frame: BinaryFrame): ByteArray {
        val header = encodeBinaryHeader(frame)
        return header + frame.data
    }
}
