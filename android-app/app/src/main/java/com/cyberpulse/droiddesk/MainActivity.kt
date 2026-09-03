package com.cyberpulse.droiddesk

import android.os.BatteryManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.drawable.toBitmap
import com.cyberpulse.droiddesk.data.DesktopApi
import com.cyberpulse.droiddesk.data.DevicePrefs
import com.cyberpulse.droiddesk.data.SavedConnection
import com.cyberpulse.droiddesk.ui.DroidDeskTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter


data class InstalledApp(
    val label: String,
    val packageName: String,
    val icon: ImageBitmap,
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DroidDeskTheme {
                DroidDeskRoot(
                    openSettings = { startActivity(Intent(Settings.ACTION_SETTINGS)) },
                    openFiles = {
                        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                            type = "*/*"
                            addCategory(Intent.CATEGORY_OPENABLE)
                        }
                        runCatching { startActivity(intent) }
                    },
                    showHome = {
                        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                        startActivity(intent)
                    },
                )
            }
        }
    }
}

@Composable
private fun DroidDeskRoot(
    openSettings: () -> Unit,
    openFiles: () -> Unit,
    showHome: () -> Unit,
) {
    val context = LocalContext.current
    val prefs = remember { DevicePrefs(context) }
    val api = remember { DesktopApi() }
    var connection by remember { mutableStateOf(prefs.load()) }
    var connectionText by remember { mutableStateOf(if (connection == null) "Not connected" else "Connecting…") }
    var showConnect by remember { mutableStateOf(connection == null) }
    var appRefresh by remember { mutableIntStateOf(0) }

    val apps by produceState(initialValue = emptyList(), appRefresh) {
        value = withContext(Dispatchers.IO) { loadLaunchableApps(context) }
    }

    LaunchedEffect(connection) {
        val active = connection ?: return@LaunchedEffect
        while (isActive) {
            try {
                api.updateStatus(
                    connection = active,
                    deviceName = Build.MODEL.ifBlank { "Android device" },
                    androidVersion = Build.VERSION.RELEASE,
                    batteryLevel = batteryLevel(context),
                )
                val commands = api.commands(active, prefs.lastCommandId)
                for (command in commands) {
                    val result = when (command.type) {
                        "SHOW_HOME" -> {
                            showHome()
                            "completed"
                        }
                        "OPEN_SETTINGS" -> {
                            openSettings()
                            "completed"
                        }
                        "SYNC_NOW" -> "completed"
                        else -> "ignored: command is not allowlisted"
                    }
                    api.acknowledge(active, command.id, result)
                    prefs.lastCommandId = command.id
                }
                connectionText = "Connected"
            } catch (_: Exception) {
                connectionText = "Controller offline"
            }
            delay(5_000)
        }
    }

    DesktopHome(
        apps = apps,
        connectionText = connectionText,
        onLaunchApp = { packageName ->
            context.packageManager.getLaunchIntentForPackage(packageName)?.let(context::startActivity)
        },
        onOpenFiles = openFiles,
        onOpenSettings = openSettings,
        onConnect = { showConnect = true },
        onRefresh = { appRefresh++ },
    )

    if (showConnect) {
        ConnectionPanel(
            current = connection,
            onDismiss = { if (connection != null) showConnect = false },
            onPaired = {
                prefs.save(it)
                prefs.lastCommandId = 0
                connection = it
                connectionText = "Connected"
                showConnect = false
            },
            onDisconnect = {
                prefs.clear()
                connection = null
                connectionText = "Not connected"
            },
            api = api,
        )
    }
}

@Composable
private fun DesktopHome(
    apps: List<InstalledApp>,
    connectionText: String,
    onLaunchApp: (String) -> Unit,
    onOpenFiles: () -> Unit,
    onOpenSettings: () -> Unit,
    onConnect: () -> Unit,
    onRefresh: () -> Unit,
) {
    var timeText by remember { mutableStateOf("") }
    var dateText by remember { mutableStateOf("") }
    LaunchedEffect(Unit) {
        val timeFormatter = DateTimeFormatter.ofPattern("HH:mm")
        val dateFormatter = DateTimeFormatter.ofPattern("EEE, d MMM")
        while (isActive) {
            val now = LocalDateTime.now()
            timeText = now.format(timeFormatter)
            dateText = now.format(dateFormatter)
            delay(1_000)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.linearGradient(
                    colors = listOf(Color(0xFF071019), Color(0xFF0A1D2C), Color(0xFF10142A)),
                )
            )
            .statusBarsPadding()
            .navigationBarsPadding(),
    ) {
        Box(
            modifier = Modifier
                .size(280.dp)
                .align(Alignment.TopEnd)
                .background(
                    Brush.radialGradient(listOf(Color(0x334F8CFF), Color.Transparent)),
                    CircleShape,
                )
        )

        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 22.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text("DROIDDESK", fontSize = 18.sp, fontWeight = FontWeight.ExtraBold,
                        color = MaterialTheme.colorScheme.primary)
                    Text("Android workspace", fontSize = 12.sp, color = Color(0xFF8AA6B8))
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Wifi, contentDescription = null,
                        tint = if (connectionText == "Connected") Color(0xFF4AF0A7) else Color(0xFF8AA6B8),
                        modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(connectionText, fontSize = 12.sp, color = Color(0xFFB9D0DF))
                    Spacer(Modifier.width(18.dp))
                    Column(horizontalAlignment = Alignment.End) {
                        Text(timeText, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                        Text(dateText, fontSize = 11.sp, color = Color(0xFF8AA6B8))
                    }
                }
            }

            Text(
                text = "Applications",
                modifier = Modifier.padding(horizontal = 22.dp, vertical = 8.dp),
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                color = Color(0xFFD6ECF7),
            )

            LazyVerticalGrid(
                columns = GridCells.Adaptive(92.dp),
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(apps, key = { it.packageName }) { app ->
                    AppTile(app, onLaunchApp)
                }
            }

            Surface(
                modifier = Modifier
                    .align(Alignment.CenterHorizontally)
                    .padding(14.dp),
                color = Color(0xDD0D1B28),
                shape = RoundedCornerShape(22.dp),
                shadowElevation = 12.dp,
                tonalElevation = 4.dp,
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    DockButton(Icons.Default.Folder, "Files", onOpenFiles)
                    DockButton(Icons.Default.Link, "Connect", onConnect)
                    DockButton(Icons.Default.Sync, "Refresh", onRefresh)
                    DockButton(Icons.Default.Settings, "Settings", onOpenSettings)
                }
            }
        }
    }
}

@Composable
private fun AppTile(app: InstalledApp, onLaunch: (String) -> Unit) {
    Column(
        modifier = Modifier
            .clip(RoundedCornerShape(16.dp))
            .clickable { onLaunch(app.packageName) }
            .padding(vertical = 10.dp, horizontal = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Surface(shape = RoundedCornerShape(15.dp), color = Color(0x221F4058)) {
            Image(
                bitmap = app.icon,
                contentDescription = app.label,
                contentScale = ContentScale.Fit,
                modifier = Modifier.padding(5.dp).size(48.dp),
            )
        }
        Spacer(Modifier.height(7.dp))
        Text(
            app.label,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            textAlign = TextAlign.Center,
            fontSize = 11.sp,
            color = Color(0xFFD6ECF7),
        )
    }
}

@Composable
private fun DockButton(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, action: () -> Unit) {
    IconButton(onClick = action, modifier = Modifier.size(54.dp)) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(icon, contentDescription = label, modifier = Modifier.size(22.dp),
                tint = MaterialTheme.colorScheme.primary)
            Text(label, fontSize = 9.sp, color = Color(0xFFB9D0DF))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ConnectionPanel(
    current: SavedConnection?,
    onDismiss: () -> Unit,
    onPaired: (SavedConnection) -> Unit,
    onDisconnect: () -> Unit,
    api: DesktopApi,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var host by remember { mutableStateOf(current?.host ?: "http://192.168.1.2:8765") }
    var code by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xCC02070C))
            .clickable(enabled = current != null, onClick = onDismiss),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            modifier = Modifier
                .padding(22.dp)
                .fillMaxWidth()
                .clickable(enabled = false) {},
            color = Color(0xFF0D1B28),
            shape = RoundedCornerShape(26.dp),
            shadowElevation = 20.dp,
        ) {
            Column(modifier = Modifier.padding(24.dp)) {
                Text("Connect to Windows", fontSize = 23.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Text(
                    "Open DroidDesk on Windows, then enter its address and one-time code.",
                    color = Color(0xFF8AA6B8), fontSize = 13.sp,
                )
                Spacer(Modifier.height(20.dp))
                OutlinedTextField(
                    value = host,
                    onValueChange = { host = it; error = null },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Windows address") },
                    singleLine = true,
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = code,
                    onValueChange = { value -> code = value.filter(Char::isDigit).take(6); error = null },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Six-digit code") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                )
                if (error != null) {
                    Text(error.orEmpty(), color = MaterialTheme.colorScheme.error,
                        fontSize = 12.sp, modifier = Modifier.padding(top = 10.dp))
                }
                Spacer(Modifier.height(20.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    if (current != null) {
                        OutlinedButton(onClick = { onDisconnect(); code = "" }) {
                            Text("Disconnect")
                        }
                        Spacer(Modifier.width(8.dp))
                        OutlinedButton(onClick = onDismiss) { Text("Close") }
                        Spacer(Modifier.width(8.dp))
                    }
                    Button(
                        enabled = !busy && code.length == 6,
                        onClick = {
                            busy = true
                            error = null
                            scope.launch {
                                try {
                                    onPaired(
                                        api.pair(
                                            host,
                                            code,
                                            Build.MODEL.ifBlank { "Android device" },
                                            Build.VERSION.RELEASE,
                                        )
                                    )
                                } catch (failure: Exception) {
                                    error = failure.message ?: "Could not connect"
                                } finally {
                                    busy = false
                                }
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.secondary),
                    ) {
                        if (busy) {
                            CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp,
                                color = Color.White)
                            Spacer(Modifier.width(8.dp))
                        }
                        Text(if (current == null) "Pair" else "Pair again")
                    }
                }
            }
        }
    }
}

private fun loadLaunchableApps(context: Context): List<InstalledApp> {
    val manager = context.packageManager
    val query = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
    return manager.queryIntentActivities(query, PackageManager.MATCH_ALL)
        .asSequence()
        .filter { it.activityInfo.packageName != context.packageName }
        .distinctBy { it.activityInfo.packageName }
        .mapNotNull { info ->
            runCatching {
                InstalledApp(
                    label = info.loadLabel(manager).toString(),
                    packageName = info.activityInfo.packageName,
                    icon = info.loadIcon(manager).toBitmap(96, 96).asImageBitmap(),
                )
            }.getOrNull()
        }
        .sortedBy { it.label.lowercase() }
        .toList()
}

private fun batteryLevel(context: Context): Int {
    val manager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
    return manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY).coerceIn(0, 100)
}
