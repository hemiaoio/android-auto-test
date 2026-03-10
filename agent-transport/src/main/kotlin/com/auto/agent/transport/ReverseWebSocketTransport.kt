package com.auto.agent.transport

import com.auto.agent.protocol.Message
import com.auto.agent.protocol.MessageType
import io.ktor.client.*
import io.ktor.client.engine.okhttp.*
import io.ktor.client.plugins.websocket.*
import io.ktor.websocket.*
import kotlin.coroutines.coroutineContext
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/**
 * 反向 WebSocket 传输层：设备作为客户端连接 PC 服务器。
 *
 * 使用单条 WebSocket 多路复用：Frame.Text = JSON 消息，Frame.Binary = 二进制帧。
 * 连接后先发 agent.register 握手，等待 agent.registered 确认后进入正常消息循环。
 * 断线后自动指数退避重连。
 */
class ReverseWebSocketTransport : TransportServer {

    private val codec = MessageCodec()
    private lateinit var config: TransportConfig

    private var messageHandler: (suspend (Message) -> Message?)? = null
    private var binaryHandler: (suspend (BinaryFrame) -> BinaryFrame?)? = null

    private val eventFlow = MutableSharedFlow<Message>(extraBufferCapacity = 64)

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var connectionJob: Job? = null
    private var session: WebSocketSession? = null

    @Volatile
    private var _running = false

    override val isRunning: Boolean
        get() = _running

    override suspend fun start(config: TransportConfig) {
        require(config.serverUrl.isNotBlank()) { "serverUrl must be set for CLIENT mode" }
        require(config.deviceId.isNotBlank()) { "deviceId must be set for CLIENT mode" }
        this.config = config
        _running = true
        connectionJob = scope.launch { connectLoop() }
    }

    override suspend fun stop() {
        _running = false
        connectionJob?.cancel()
        session?.close(CloseReason(CloseReason.Codes.GOING_AWAY, "Agent stopping"))
        session = null
        scope.cancel()
    }

    override fun onMessage(handler: suspend (Message) -> Message?) {
        this.messageHandler = handler
    }

    override fun onBinaryMessage(handler: suspend (BinaryFrame) -> BinaryFrame?) {
        this.binaryHandler = handler
    }

    override suspend fun sendEvent(message: Message) {
        eventFlow.emit(message)
    }

    override suspend fun sendBinary(frame: BinaryFrame) {
        try {
            val encoded = codec.encodeBinaryFrame(frame)
            session?.send(Frame.Binary(true, encoded))
        } catch (_: Exception) { }
    }

    override suspend fun broadcast(message: Message) {
        try {
            session?.send(Frame.Text(codec.encode(message)))
        } catch (_: Exception) { }
    }

    // ---------- 连接循环 ----------

    private suspend fun connectLoop() {
        var attempt = 0
        while (_running && coroutineContext.isActive) {
            try {
                attempt++
                doConnect()
                // 正常退出 doConnect 意味着连接关闭，重置计数
                attempt = 0
            } catch (_: CancellationException) {
                break
            } catch (_: Exception) {
                // 连接失败或异常断开
            }
            if (!_running) break
            // 指数退避
            val delay = (config.reconnectBaseDelayMs * (1L shl minOf(attempt, 6)))
                .coerceAtMost(config.reconnectMaxDelayMs)
            if (attempt > config.reconnectMaxAttempts) break
            delay(delay)
        }
    }

    private suspend fun doConnect() {
        val client = HttpClient(OkHttp) {
            install(WebSockets) {
                pingInterval = config.heartbeatIntervalMs
            }
        }

        try {
            client.webSocket(config.serverUrl) {
                session = this

                // ---- 握手：发送 agent.register ----
                val registerMsg = Message.event(
                    method = "agent.register",
                    params = JsonObject(mapOf(
                        "deviceId" to JsonPrimitive(config.deviceId),
                        "protocolVersion" to JsonPrimitive("1.0"),
                        "agentVersion" to JsonPrimitive("1.0.0")
                    ))
                )
                send(Frame.Text(codec.encode(registerMsg)))

                // 等待 agent.registered 确认（5 秒超时）
                val confirmed = withTimeoutOrNull(5_000L) {
                    for (frame in incoming) {
                        if (frame is Frame.Text) {
                            val msg = codec.decode(frame.readText())
                            if (msg.method == "agent.registered") {
                                return@withTimeoutOrNull true
                            }
                        }
                    }
                    false
                }
                if (confirmed != true) {
                    throw IllegalStateException("Registration not confirmed by server")
                }

                // ---- 启动事件转发协程 ----
                val eventJob = launch {
                    eventFlow.collect { event ->
                        try {
                            send(Frame.Text(codec.encode(event)))
                        } catch (_: Exception) { }
                    }
                }

                // ---- 主消息循环 ----
                try {
                    for (frame in incoming) {
                        when (frame) {
                            is Frame.Text -> {
                                val text = frame.readText()
                                try {
                                    val request = codec.decode(text)
                                    if (request.type == MessageType.REQUEST) {
                                        val response = messageHandler?.invoke(request)
                                        if (response != null) {
                                            send(Frame.Text(codec.encode(response)))
                                        }
                                    }
                                } catch (_: Exception) { }
                            }
                            is Frame.Binary -> {
                                // 处理 PC 发来的二进制数据（如文件推送）
                            }
                            else -> { }
                        }
                    }
                } finally {
                    eventJob.cancel()
                    session = null
                }
            }
        } finally {
            client.close()
        }
    }
}
