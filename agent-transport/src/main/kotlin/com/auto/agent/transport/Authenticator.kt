package com.auto.agent.transport

import java.security.SecureRandom

class Authenticator(private val config: TransportConfig) {

    private val activeSessions = mutableMapOf<String, SessionInfo>()
    private val random = SecureRandom()

    data class SessionInfo(
        val sessionId: String,
        val clientId: String,
        val connectedAt: Long = System.currentTimeMillis(),
        var lastActivity: Long = System.currentTimeMillis()
    )

    fun authenticate(token: String?, clientId: String): Result<SessionInfo> {
        // If no auth token configured, allow all connections
        if (config.authToken == null) {
            return Result.success(createSession(clientId))
        }

        if (token == null || token != config.authToken) {
            return Result.failure(AuthenticationException("Invalid authentication token"))
        }

        return Result.success(createSession(clientId))
    }

    fun validateSession(sessionId: String): Boolean {
        val session = activeSessions[sessionId] ?: return false
        session.lastActivity = System.currentTimeMillis()
        return true
    }

    fun invalidateSession(sessionId: String) {
        activeSessions.remove(sessionId)
    }

    fun getSession(sessionId: String): SessionInfo? = activeSessions[sessionId]

    val activeSessionCount: Int get() = activeSessions.size

    private fun createSession(clientId: String): SessionInfo {
        val sessionId = generateSessionId()
        val session = SessionInfo(sessionId = sessionId, clientId = clientId)
        activeSessions[sessionId] = session
        return session
    }

    private fun generateSessionId(): String {
        val bytes = ByteArray(32)
        random.nextBytes(bytes)
        return bytes.joinToString("") { "%02x".format(it) }
    }
}

class AuthenticationException(message: String) : Exception(message)
