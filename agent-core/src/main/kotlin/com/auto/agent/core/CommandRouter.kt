package com.auto.agent.core

import com.auto.agent.protocol.Message
import com.auto.agent.protocol.MessageError
import com.auto.agent.protocol.ErrorCodes
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import java.util.concurrent.ConcurrentHashMap

/**
 * Routes incoming protocol messages to the appropriate handler.
 */
class CommandRouter {

    private val handlers = ConcurrentHashMap<String, CommandHandler>()

    fun register(method: String, handler: CommandHandler) {
        handlers[method] = handler
    }

    fun register(handler: CommandHandler) {
        handlers[handler.method] = handler
    }

    fun unregister(method: String) {
        handlers.remove(method)
    }

    suspend fun route(request: Message): Message {
        val method = request.method
            ?: return Message.response(
                requestId = request.id,
                method = "error",
                error = MessageError(
                    code = ErrorCodes.Internal.ERROR,
                    category = "INTERNAL",
                    message = "Missing method in request"
                )
            )

        val handler = handlers[method]
            ?: return Message.response(
                requestId = request.id,
                method = method,
                error = MessageError(
                    code = ErrorCodes.Internal.NOT_IMPLEMENTED,
                    category = "INTERNAL",
                    message = "Unknown method: $method"
                )
            )

        return try {
            val validationResult = handler.validate(request.params)
            if (!validationResult.isValid) {
                return Message.response(
                    requestId = request.id,
                    method = method,
                    error = MessageError(
                        code = ErrorCodes.Internal.ERROR,
                        category = "INTERNAL",
                        message = "Validation failed: ${validationResult.error}"
                    )
                )
            }

            val result = handler.handle(request.params, RequestContext(request.id, request.metadata))
            Message.response(
                requestId = request.id,
                method = method,
                result = result
            )
        } catch (e: AgentException) {
            Message.response(
                requestId = request.id,
                method = method,
                error = MessageError(
                    code = e.code,
                    category = ErrorCodes.categoryOf(e.code),
                    message = e.message ?: "Unknown error",
                    recoverable = ErrorCodes.isRecoverable(e.code)
                )
            )
        } catch (e: Exception) {
            Message.response(
                requestId = request.id,
                method = method,
                error = MessageError(
                    code = ErrorCodes.Internal.UNKNOWN,
                    category = "INTERNAL",
                    message = "Internal error: ${e.message}"
                )
            )
        }
    }

    val registeredMethods: Set<String> get() = handlers.keys.toSet()
}

interface CommandHandler {
    val method: String
    suspend fun handle(params: JsonObject?, context: RequestContext): JsonElement?
    fun validate(params: JsonObject?): ValidationResult = ValidationResult.ok()
}

data class RequestContext(
    val requestId: String,
    val metadata: com.auto.agent.protocol.MessageMetadata?
)

data class ValidationResult(
    val isValid: Boolean,
    val error: String? = null
) {
    companion object {
        fun ok() = ValidationResult(true)
        fun fail(error: String) = ValidationResult(false, error)
    }
}

open class AgentException(
    val code: Int,
    override val message: String,
    override val cause: Throwable? = null
) : Exception(message, cause)
