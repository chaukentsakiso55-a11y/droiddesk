package com.cyberpulse.droiddesk.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DroidDeskColors = darkColorScheme(
    primary = Color(0xFF3CE7FF),
    onPrimary = Color(0xFF001F27),
    secondary = Color(0xFF6E97FF),
    background = Color(0xFF071019),
    surface = Color(0xFF0D1B28),
    surfaceVariant = Color(0xFF102638),
    onBackground = Color(0xFFEDFAFF),
    onSurface = Color(0xFFEDFAFF),
    outline = Color(0xFF315065),
    error = Color(0xFFFF6B7A),
)

@Composable
fun DroidDeskTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DroidDeskColors,
        typography = androidx.compose.material3.Typography(),
        content = content,
    )
}

