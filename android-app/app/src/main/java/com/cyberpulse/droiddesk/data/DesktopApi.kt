package com.cyberpulse.droiddesk.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

data class SavedConnection(
    val host: String,
    val deviceId: String,
    val token: String,
)

data class RemoteCommand(
    val id: Int,
    val type: String,
)

class DesktopApi {
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()
    private val client = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .writeTimeout(5, TimeUnit.SECONDS)
        .build()

    suspend fun pair(
        rawHost: String,
        pairCode: String,
        deviceName: String,
        androidVersion: String,
    ): SavedConnection = withContext(Dispatchers.IO) {
        val host = normalizeHost(rawHost)
        require(pairCode.length == 6 && pairCode.all(Char::isDigit)) {
            "Enter the six-digit pairing code"
        }
        val payload = JSONObject()
            .put("pairCode", pairCode)
            .put("deviceName", deviceName)
            .put("androidVersion", androidVersion)
        val request = Request.Builder()
            .url("$host/api/v1/pair")
            .post(payload.toString().toRequestBody(jsonMedia))
            .build()
        execute(request) { body ->
            val json = JSONObject(body)
            SavedConnection(
                host = host,
                deviceId = json.getString("deviceId"),
                token = json.getString("token"),
            )
        }
    }

    suspend fun updateStatus(
        connection: SavedConnection,
        deviceName: String,
        androidVersion: String,
        batteryLevel: Int,
    ) = withContext(Dispatchers.IO) {
        val payload = JSONObject()
            .put("deviceName", deviceName)
            .put("androidVersion", androidVersion)
            .put("batteryLevel", batteryLevel.coerceIn(0, 100))
        val request = authorized(connection, "/api/v1/status")
            .post(payload.toString().toRequestBody(jsonMedia))
            .build()
        execute(request) { Unit }
    }

    suspend fun commands(connection: SavedConnection, after: Int): List<RemoteCommand> =
        withContext(Dispatchers.IO) {
            val request = authorized(connection, "/api/v1/commands?after=${after.coerceAtLeast(0)}")
                .get()
                .build()
            execute(request) { body ->
                val array = JSONObject(body).getJSONArray("commands")
                buildList {
                    for (index in 0 until array.length()) {
                        val item = array.getJSONObject(index)
                        add(RemoteCommand(item.getInt("id"), item.getString("type")))
                    }
                }
            }
        }

    suspend fun acknowledge(connection: SavedConnection, commandId: Int, result: String) =
        withContext(Dispatchers.IO) {
            val payload = JSONObject().put("result", result.take(120))
            val request = authorized(connection, "/api/v1/commands/$commandId/ack")
                .post(payload.toString().toRequestBody(jsonMedia))
                .build()
            execute(request) { Unit }
        }

    private fun authorized(connection: SavedConnection, path: String): Request.Builder =
        Request.Builder()
            .url(connection.host.trimEnd('/') + path)
            .header("Authorization", "Bearer ${connection.token}")

    private fun normalizeHost(raw: String): String {
        var value = raw.trim().trimEnd('/')
        if (!value.startsWith("http://") && !value.startsWith("https://")) {
            value = "http://$value"
        }
        val parsed = value.toHttpUrlOrNull()
            ?: throw IllegalArgumentException("Enter a valid Windows address")
        require(parsed.host.isNotBlank()) { "Enter a valid Windows address" }
        return parsed.toString().trimEnd('/')
    }

    private fun <T> execute(request: Request, transform: (String) -> T): T {
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val message = runCatching { JSONObject(body).optString("error") }.getOrNull()
                    .orEmpty()
                throw IOException(message.ifBlank { "Windows controller returned ${response.code}" })
            }
            return transform(body)
        }
    }
}
