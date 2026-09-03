package com.cyberpulse.droiddesk.data

import android.content.Context

class DevicePrefs(context: Context) {
    private val prefs = context.getSharedPreferences("droiddesk_connection", Context.MODE_PRIVATE)

    fun load(): SavedConnection? {
        val host = prefs.getString("host", null) ?: return null
        val deviceId = prefs.getString("deviceId", null) ?: return null
        val token = prefs.getString("token", null) ?: return null
        return SavedConnection(host, deviceId, token)
    }

    fun save(connection: SavedConnection) {
        prefs.edit()
            .putString("host", connection.host)
            .putString("deviceId", connection.deviceId)
            .putString("token", connection.token)
            .apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    var lastCommandId: Int
        get() = prefs.getInt("lastCommandId", 0)
        set(value) = prefs.edit().putInt("lastCommandId", value).apply()
}

