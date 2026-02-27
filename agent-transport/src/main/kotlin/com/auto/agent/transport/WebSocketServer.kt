package com.auto.agent.transport

import com.auto.agent.protocol.Message
import com.auto.agent.protocol.MessageType
import io.ktor.server.application.*
import io.ktor.server.engine.*
import io.ktor.server.netty.*
import io.ktor.server.routing.*
import io.ktor.server.websocket.*
import io.ktor.websocket.*
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.time.Duration
import java.util.concurrent.ConcurrentHashMap

class WebSocketTransportServer : TransportServer {

    private var controlServer: ApplicationEngine? = null
    private var binaryServer: ApplicationEngine? = null
    private var eventServer: ApplicationEngine? = null

    private val codec = MessageCodec()
    private lateinit var authenticator: Authenticator
    private lateinit var config: TransportConfig

    private var messageHandler: (suspend (Message) -> Message?)? = null
    private var binaryHandler: (suspend (BinaryFrame) -> BinaryFrame?)? = null

    private val eventFlow = MutableSharedFlow<Message>(extraBufferCapacity = 64)
    private val binaryOutChannel = Channel<BinaryFrame>(capacity = 16)

    private val controlSessions = ConcurrentHashMap<String, WebSocketSession>()
    private val eventSessions = ConcurrentHashMap<String, WebSocketSession>()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override val isRunning: Boolean
        get() = controlServer != null

    override suspend fun start(config: TransportConfig) {
        this.config = config
        this.authenticator = Authenticator(config)

        controlServer = embeddedServer(Netty, port = config.controlPort, host = config.host) {
            install(WebSockets) {
                pingPeriod = Duration.ofMillis(config.heartbeatIntervalMs)
                timeout = Duration.ofMillis(config.heartbeatTimeoutMs)
                maxFrameSize = Long.MAX_VALUE
                masking = false
            }
            routing {
                webSocket("/control") {
                    handleControlSession(this)
                }
            }
        }.also { it.start(wait = false) }

        binaryServer = embeddedServer(Netty, port = config.binaryPort, host = config.host) {
            install(WebSockets) {
                maxFrameSize = Long.MAX_VALUE
                masking = false
            }
            routing {
                webSocket("/binary") {
                    handleBinarySession(this)
                }
            }
        }.also { it.start(wait = false) }

        eventServer = embeddedServer(Netty, port = config.eventPort, host = config.host) {
            install(WebSockets) {
                pingPeriod = Duration.ofMillis(config.heartbeatIntervalMs)
                timeout = Duration.ofMillis(config.heartbeatTimeoutMs)
                masking = false
            }
            routing {
                webSocket("/events") {
                    handleEventSession(this)
                }
            }
        }.also { it.start(wait = false) }
    }

    override suspend fun stop() {
        scope.cancel()
        controlSessions.values.forEach { it.close(CloseReason(CloseReason.Codes.GOING_AWAY, "Server shutting down")) }
        eventSessions.values.forEach { it.close(CloseReason(CloseReason.Codes.GOING_AWAY, "Server shutting down")) }
        controlServer?.stop(1000, 2000)
        binaryServer?.stop(1000, 2000)
        eventServer?.stop(1000, 2000)
        controlServer = null
        binaryServer = null
        eventServer = null
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
        binaryOutChannel.send(frame)
    }

    override suspend fun broadcast(message: Message) {
        val text = codec.encode(message)
        controlSessions.values.forEach { session ->
            try {
                session.send(Frame.Text(text))
            } catch (_: Exception) { }
        }
    }

    private suspend fun handleControlSession(session: WebSocketSession) {
        val sessionId = java.util.UUID.randomUUID().toString()
        controlSessions[sessionId] = session

        try {
            // Send server hello
            val hello = Message.event("system.hello")
            session.send(Frame.Text(codec.encode(hello)))

            for (frame in session.incoming) {
                when (frame) {
                    is Frame.Text -> {
                        val text = frame.readText()
                        try {
                            val request = codec.decode(text)
                            val response = messageHandler?.invoke(request)
                            if (response != null) {
                                session.send(Frame.Text(codec.encode(response)))
                            }
                        } catch (e: Exception) {
                            val errorResponse = Message.response(
                                requestId = "unknown",
                                method = "error",
                                error = com.auto.agent.protocol.MessageError(
                                    code = 9001,
                                    category = "INTERNAL",
                                    message = "Failed to process message: ${e.message}"
                                )
                            )
                            session.send(Frame.Text(codec.encode(errorResponse)))
                        }
                    }
                    else -> { }
                }
            }
        } finally {
            controlSessions.remove(sessionId)
        }
    }

    private suspend fun handleBinarySession(session: WebSocketSession) {
        val sessionId = java.util.UUID.randomUUID().toString()

        // Launch sender coroutine for outgoing binary data
        val senderJob = scope.launch {
            for (frame in binaryOutChannel) {
                try {
                    val encoded = codec.encodeBinaryFrame(frame)
                    session.send(Frame.Binary(true, encoded))
                } catch (_: Exception) { }
            }
        }

        try {
            for (frame in session.incoming) {
                when (frame) {
                    is Frame.Binary -> {
                        // Handle incoming binary (e.g., file push)
                    }
                    else -> { }
                }
            }
        } finally {
            senderJob.cancel()
        }
    }

    private suspend fun handleEventSession(session: WebSocketSession) {
        val sessionId = java.util.UUID.randomUUID().toString()
        eventSessions[sessionId] = session

        try {
            eventFlow.asSharedFlow().collect { event ->
                try {
                    session.send(Frame.Text(codec.encode(event)))
                } catch (_: Exception) { }
            }
        } finally {
            eventSessions.remove(sessionId)
        }
    }
}
