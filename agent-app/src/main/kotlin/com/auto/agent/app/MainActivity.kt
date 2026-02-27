package com.auto.agent.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.appcompat.app.AppCompatActivity
import com.auto.agent.app.databinding.ActivityMainBinding
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var isAgentRunning = false
    private val logBuilder = StringBuilder()

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == AgentForegroundService.ACTION_STATUS_CHANGED) {
                isAgentRunning = intent.getBooleanExtra(AgentForegroundService.EXTRA_IS_RUNNING, false)
                updateUI()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupUI()
        checkCapabilities()
    }

    override fun onResume() {
        super.onResume()
        val filter = IntentFilter(AgentForegroundService.ACTION_STATUS_CHANGED)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusReceiver, filter, RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(statusReceiver, filter)
        }
        checkCapabilities()
    }

    override fun onPause() {
        super.onPause()
        unregisterReceiver(statusReceiver)
    }

    private fun setupUI() {
        binding.tvVersion.text = "v${BuildConfig.VERSION_NAME}"

        binding.btnToggle.setOnClickListener {
            if (isAgentRunning) {
                AgentForegroundService.stop(this)
                appendLog("Agent stopping...")
            } else {
                AgentForegroundService.start(this)
                appendLog("Agent starting...")
            }
        }

        binding.btnAccessibility.setOnClickListener {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            startActivity(intent)
        }
    }

    private fun checkCapabilities() {
        // Check root
        val isRooted = checkRoot()
        binding.tvRootStatus.text = if (isRooted) "Available" else "Not Available"
        binding.tvRootStatus.setTextColor(
            if (isRooted) 0xFF4CAF50.toInt() else 0xFFFF9800.toInt()
        )

        // Check accessibility
        val isA11y = checkAccessibilityEnabled()
        binding.tvAccessibilityStatus.text = if (isA11y) "Enabled" else "Disabled"
        binding.tvAccessibilityStatus.setTextColor(
            if (isA11y) 0xFF4CAF50.toInt() else 0xFFFF9800.toInt()
        )

        updateUI()
    }

    private fun updateUI() {
        binding.btnToggle.text = if (isAgentRunning) getString(R.string.btn_stop) else getString(R.string.btn_start)
        binding.tvAgentStatus.text = if (isAgentRunning) getString(R.string.status_running) else getString(R.string.status_idle)
        binding.tvAgentStatus.setTextColor(
            if (isAgentRunning) 0xFF4CAF50.toInt() else 0xFF757575.toInt()
        )

        if (isAgentRunning) {
            appendLog("Agent is running on port 18900")
        }
    }

    private fun checkRoot(): Boolean {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("su", "-c", "id"))
            val result = process.inputStream.bufferedReader().readText()
            process.waitFor()
            result.contains("uid=0")
        } catch (_: Exception) {
            false
        }
    }

    private fun checkAccessibilityEnabled(): Boolean {
        val enabledServices = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        return enabledServices.contains("com.auto.agent/com.auto.agent.accessibility.AgentAccessibilityService")
    }

    private fun appendLog(message: String) {
        val time = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        logBuilder.append("[$time] $message\n")
        binding.tvLogs.text = logBuilder.toString()
    }
}
