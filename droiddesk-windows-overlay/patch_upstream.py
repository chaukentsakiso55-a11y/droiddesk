#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_upstream.py <DroidDesk source root>")

root = Path(sys.argv[1]).resolve()
overlay = Path(__file__).resolve().parent

def replace_once(rel, old, new):
    path = root / rel
    text = path.read_text()
    if old not in text:
        raise RuntimeError(f"patch anchor not found in {rel}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))

def insert_before(rel, anchor, block):
    path = root / rel
    text = path.read_text()
    if anchor not in text:
        raise RuntimeError(f"insert anchor not found in {rel}: {anchor[:100]!r}")
    path.write_text(text.replace(anchor, block + anchor, 1))

def copy_file(source_name, destination):
    target = root / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(overlay / source_name, target)

replace_once(
    "app/pubspec.yaml",
    "  url_launcher: ^6.3.2\n",
    "  url_launcher: ^6.3.2\n  file_picker: ^8.1.7\n",
)

replace_once(
    "app/android/app/src/main/kotlin/com/orailnoor/droiddesk/runtime/LinuxRuntime.kt",
    "    private fun getTermuxEnv(): Map<String, String> {",
    "    internal fun getTermuxEnv(): Map<String, String> {",
)
replace_once(
    "app/android/app/src/main/kotlin/com/orailnoor/droiddesk/runtime/LinuxRuntime.kt",
    "    private fun installRepoPackages(): Boolean {",
    "    internal fun installRepoPackages(): Boolean {",
)
replace_once(
    "app/android/app/src/main/kotlin/com/orailnoor/droiddesk/runtime/LinuxRuntime.kt",
    "    private fun installPackageGroup(cmd: String): Boolean {",
    "    internal fun installPackageGroup(cmd: String): Boolean {",
)

bridge = "app/lib/services/platform_bridge.dart"
replace_once(
    bridge,
    "  static Function(double progress, String status)? onOptionalInstallProgress;\n",
    "  static Function(double progress, String status)? onOptionalInstallProgress;\n"
    "  static Function(double progress, String status)? onWindowsProgress;\n",
)
insert_before(
    bridge,
    "        case 'onTerminalOutput':\n",
    """        case 'onWindowsProgress':
          final args = call.arguments as Map;
          onWindowsProgress?.call(
            (args['progress'] as num).toDouble(),
            args['status'] as String,
          );
          break;
""",
)
insert_before(
    bridge,
    "  // ── Battery Optimization ──\n",
    """  // ── Windows VM ──

  static Future<Map<String, dynamic>> getWindowsStatus() async {
    final result = await _channel.invokeMethod('getWindowsStatus');
    return Map<String, dynamic>.from(result);
  }

  static Future<bool> prepareWindowsRuntime() async {
    return await _channel.invokeMethod<bool>('prepareWindowsRuntime') ?? false;
  }

  static Future<bool> importWindowsIso(String path) async {
    return await _channel.invokeMethod<bool>('importWindowsIso', {
          'path': path,
        }) ??
        false;
  }

  static Future<bool> removeWindowsIso() async {
    return await _channel.invokeMethod<bool>('removeWindowsIso') ?? false;
  }

  static Future<bool> createWindowsDisk(int sizeGb) async {
    return await _channel.invokeMethod<bool>('createWindowsDisk', {
          'sizeGb': sizeGb,
        }) ??
        false;
  }

  static Future<bool> startWindows({
    int ramMb = 2048,
    int cpuCount = 2,
    bool bootInstaller = true,
  }) async {
    return await _channel.invokeMethod<bool>('startWindows', {
          'ramMb': ramMb,
          'cpuCount': cpuCount,
          'bootInstaller': bootInstaller,
        }) ??
        false;
  }

  static Future<bool> stopWindows() async {
    return await _channel.invokeMethod<bool>('stopWindows') ?? false;
  }

""",
)

main = "app/lib/main.dart"
replace_once(
    main,
    "import 'package:droiddesk/screens/home_screen.dart';\n",
    "import 'package:droiddesk/screens/home_screen.dart';\n"
    "import 'package:droiddesk/screens/windows_screen.dart';\n",
)
replace_once(
    main,
    """      home: Consumer<AppState>(
        builder: (context, state, _) {
          // Route to setup wizard or home based on bootstrap state
          if (state.isSetupComplete) {
            return const HomeScreen();
          }
          return const WelcomeScreen();
        },
      ),
""",
    "      home: const DroidDeskShell(),\n",
)
with (root / main).open("a") as handle:
    handle.write(
        """

class DroidDeskShell extends StatefulWidget {
  const DroidDeskShell({super.key});

  @override
  State<DroidDeskShell> createState() => _DroidDeskShellState();
}

class _DroidDeskShellState extends State<DroidDeskShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final linuxScreen = state.isSetupComplete
        ? const HomeScreen()
        : const WelcomeScreen();

    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [
          linuxScreen,
          const WindowsScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (index) => setState(() => _index = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.terminal_rounded),
            selectedIcon: Icon(Icons.desktop_mac_rounded),
            label: 'Linux',
          ),
          NavigationDestination(
            icon: Icon(Icons.window_outlined),
            selectedIcon: Icon(Icons.window_rounded),
            label: 'Windows',
          ),
        ],
      ),
    );
  }
}
"""
    )

activity = "app/android/app/src/main/kotlin/com/orailnoor/droiddesk/MainActivity.kt"
replace_once(
    activity,
    "import com.orailnoor.droiddesk.runtime.ChrootRuntime\n",
    "import com.orailnoor.droiddesk.runtime.ChrootRuntime\n"
    "import com.orailnoor.droiddesk.runtime.WindowsRuntime\n",
)
replace_once(
    activity,
    "    private lateinit var chrootRuntime: ChrootRuntime\n",
    "    private lateinit var chrootRuntime: ChrootRuntime\n"
    "    private lateinit var windowsRuntime: WindowsRuntime\n",
)
replace_once(
    activity,
    "        chrootRuntime = ChrootRuntime(this)\n",
    "        chrootRuntime = ChrootRuntime(this)\n"
    "        windowsRuntime = WindowsRuntime(this)\n",
)

windows_cases = """                // ── Windows VM ──
                "getWindowsStatus" -> {
                    result.success(windowsRuntime.status())
                }

                "prepareWindowsRuntime" -> {
                    thread(name = "prepare-windows-runtime") {
                        val ok = windowsRuntime.prepareRuntime { progress, status ->
                            runOnUiThread {
                                MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
                                    .invokeMethod(
                                        "onWindowsProgress",
                                        mapOf("progress" to progress, "status" to status),
                                    )
                            }
                        }
                        runOnUiThread { result.success(ok) }
                    }
                }

                "importWindowsIso" -> {
                    val path = call.argument<String>("path") ?: ""
                    thread(name = "import-windows-iso") {
                        val ok = windowsRuntime.importIso(path) { progress, status ->
                            runOnUiThread {
                                MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
                                    .invokeMethod(
                                        "onWindowsProgress",
                                        mapOf("progress" to progress, "status" to status),
                                    )
                            }
                        }
                        runOnUiThread { result.success(ok) }
                    }
                }

                "removeWindowsIso" -> {
                    result.success(windowsRuntime.removeIso())
                }

                "createWindowsDisk" -> {
                    val sizeGb = call.argument<Int>("sizeGb") ?: 64
                    thread(name = "create-windows-disk") {
                        val ok = windowsRuntime.createDisk(sizeGb) { progress, status ->
                            runOnUiThread {
                                MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
                                    .invokeMethod(
                                        "onWindowsProgress",
                                        mapOf("progress" to progress, "status" to status),
                                    )
                            }
                        }
                        runOnUiThread { result.success(ok) }
                    }
                }

                "startWindows" -> {
                    val ramMb = call.argument<Int>("ramMb") ?: 2048
                    val cpuCount = call.argument<Int>("cpuCount") ?: 2
                    val bootInstaller = call.argument<Boolean>("bootInstaller") ?: true
                    val vmStatus = windowsRuntime.status()
                    val ready = vmStatus["prepared"] == true &&
                        vmStatus["diskExists"] == true &&
                        (!bootInstaller || vmStatus["isoExists"] == true)
                    if (!ready) {
                        result.success(false)
                    } else {
                        windowsRuntime.saveLaunchConfig(ramMb, cpuCount, bootInstaller)
                        startForegroundService()
                        val intent = Intent(
                            this@MainActivity,
                            com.orailnoor.droiddesk.view.DesktopActivity::class.java,
                        ).apply {
                            putExtra("startSession", true)
                            putExtra("mode", "windows")
                        }
                        startActivity(intent)
                        result.success(true)
                    }
                }

                "stopWindows" -> {
                    thread(name = "stop-windows-session") {
                        windowsRuntime.stopSession()
                        stopService(Intent(this@MainActivity, X11ServerService::class.java))
                        stopForegroundService()
                        runOnUiThread { result.success(true) }
                    }
                }

"""
insert_before(
    activity,
    "                // ── Start Linux session ──\n",
    windows_cases,
)

desktop = "app/android/app/src/main/kotlin/com/orailnoor/droiddesk/view/DesktopActivity.kt"
replace_once(
    desktop,
    "import com.orailnoor.droiddesk.runtime.ChrootRuntime\n",
    "import com.orailnoor.droiddesk.runtime.ChrootRuntime\n"
    "import com.orailnoor.droiddesk.runtime.WindowsRuntime\n",
)
replace_once(
    desktop,
    "    private lateinit var chrootRuntime: ChrootRuntime\n",
    "    private lateinit var chrootRuntime: ChrootRuntime\n"
    "    private lateinit var windowsRuntime: WindowsRuntime\n",
)
replace_once(
    desktop,
    "        chrootRuntime = ChrootRuntime(this)\n",
    "        chrootRuntime = ChrootRuntime(this)\n"
    "        windowsRuntime = WindowsRuntime(this)\n",
)
replace_once(
    desktop,
    """                if (sessionMode == "chroot") {
                    chrootRuntime.startSession(desktopEnv)
                } else {
                    linuxRuntime.startSession(desktopEnv, "x11")
                }
""",
    """                when (sessionMode) {
                    "chroot" -> chrootRuntime.startSession(desktopEnv)
                    "windows" -> windowsRuntime.startSession()
                    else -> linuxRuntime.startSession(desktopEnv, "x11")
                }
""",
)

copy_file(
    "WindowsRuntime.kt",
    "app/android/app/src/main/kotlin/com/orailnoor/droiddesk/runtime/WindowsRuntime.kt",
)
copy_file(
    "windows_screen.dart",
    "app/lib/screens/windows_screen.dart",
)

notice = root / "DROIDDESK_WINDOWS_DERIVATIVE_NOTICE.md"
notice.write_text(
    """# DroidDesk Windows derivative

This generated Android build is based on the GPL-3.0-licensed DroidDesk project
by orailnoor and includes a Windows virtual-machine mode added by Cyber Pulse.
The generated derivative remains subject to GPL-3.0. Microsoft Windows and a
Windows license are not included. Users must supply their own legitimate
Windows installation media and license where required.
"""
)

print("DroidDesk Windows overlay applied")
