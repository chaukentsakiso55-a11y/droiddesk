from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()

def replace_once(path, old, new):
    p = root / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected block not found in {path}")
    if text.count(old) != 1:
        raise SystemExit(f"Expected exactly one match in {path}, found {text.count(old)}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(
    "app/android/app/src/main/java/com/termux/x11/MainActivity.java",
    """        if (lorieView == null) {
            lorieView = new LorieView(context);
        }
""",
    """        if (lorieView == null) {
            lorieView = new LorieView(context);
            lorieView.reloadPreferences(getPrefs());
        }
""",
)

replace_once(
    "app/android/app/src/main/kotlin/com/orailnoor/droiddesk/runtime/LinuxRuntime.kt",
    """        // mesa-zink pulls the Vulkan loader selected by the active Termux repo.
        // Current repositories use vulkan-loader-generic, which provides and
        // conflicts with the older vulkan-loader-android package name.
        if (!installPackageGroup("pkg install -y mesa-zink")) {
            // Graphics acceleration is optional. A desktop with llvmpipe is much
            // better UX than failing setup because a vendor Vulkan stack is not
            // compatible with the current Mesa package set.
            Log.w(TAG, "Mesa/Zink install unavailable; continuing with software rendering")
            installPackageGroup("dpkg --configure -a")
        }

        // Turnip/Freedreno is the hardware path for Qualcomm Adreno. Do not
        // install or force that ICD on Mali/PowerVR devices.
        if (hasAdrenoGpu()) {
            onProgress?.invoke(0.78, "Installing Adreno hardware acceleration...")
            installPackageGroup("pkg install -y mesa-vulkan-icd-freedreno")
        }
""",
    """        // Modern Termux Mesa includes Zink in the main mesa package.
        // Avoid mesa-zink because older builds can force a Mesa downgrade.
        if (!installPackageGroup("pkg install -y mesa")) {
            Log.w(TAG, "Mesa install unavailable; continuing with software rendering")
            installPackageGroup("dpkg --configure -a")
        }

        // Use the loader that matches the GPU path. Adreno/Turnip requires
        // the generic Vulkan loader; other devices keep the Android loader.
        if (hasAdrenoGpu()) {
            onProgress?.invoke(0.78, "Installing Adreno hardware acceleration...")
            if (!installPackageGroup("pkg install -y vulkan-loader-generic mesa-vulkan-icd-freedreno")) {
                Log.w(TAG, "Adreno Vulkan stack unavailable; continuing with software rendering")
                installPackageGroup("dpkg --configure -a")
            }
        } else {
            installPackageGroup("pkg install -y vulkan-loader-android")
        }
""",
)

replace_once(
    "app/pubspec.yaml",
    "version: 0.1.0\n",
    "version: 1.0.2+102\n",
)

print("Applied DroidDesk Enhanced Linux fixes.")
