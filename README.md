# DroidDesk

DroidDesk is a connected Android and Windows workspace from Cyber Pulse.

- **Android:** a native desktop-style launcher with an app grid, taskbar, clock,
  device status, and secure pairing.
- **Windows:** a lightweight control centre that discovers its LAN address,
  generates one-time pairing codes, shows connected phones, and sends a small
  allowlist of safe commands.

The first release is a LAN MVP. Both devices must be on the same trusted Wi-Fi
network. No cloud account or API key is required.

## What works

- Use DroidDesk as an Android home launcher or open it as a normal app.
- Launch installed Android apps from a desktop-style grid.
- Pair Android to Windows with a six-digit code that expires after five minutes.
- Keep a persistent 256-bit-equivalent bearer token after pairing.
- See connection, battery, Android version, and last-seen status on Windows.
- Send `Show home`, `Open settings`, and `Sync now` commands.
- Build the Android debug APK and Windows EXE in GitHub Actions.
- Run Python protocol and security tests in CI.

## Repository layout

```text
android-app/    Kotlin + Jetpack Compose Android launcher
windows-app/    Python standard-library Windows controller
docs/           Protocol and security design
.github/        Tests and artifact builds
```

## Run the Windows controller

Python 3.11 or newer is recommended.

```powershell
cd windows-app
python droiddesk.py
```

The app uses only the Python standard library at runtime. If Windows Defender
Firewall asks, allow access on **Private networks** only.

To create the EXE locally:

```powershell
python -m pip install -r requirements-build.txt
pyinstaller --clean --noconfirm DroidDesk.spec
```

The result is `dist/DroidDesk.exe`.

## Run the Android launcher

1. Open `android-app` in Android Studio.
2. Wait for Gradle sync.
3. Run the `app` configuration on Android 8.0 or newer.
4. Press Home and choose DroidDesk if you want it as the default launcher.
5. Open **Connect**, enter the Windows address and six-digit code, then pair.

For a physical phone, use the exact address shown in the Windows controller,
for example `http://192.168.1.20:8765`. The Android emulator normally uses
`http://10.0.2.2:8765` to reach the same computer.

## Download CI builds

Open the repository's **Actions** tab, choose the latest successful **Build
artifacts** run, and download:

- `DroidDesk-Android-debug` for the APK
- `DroidDesk-Windows` for the EXE

Debug APKs are for testing. Before public distribution, create a private Android
signing key and a signed release workflow.

## Trust boundary

DroidDesk intentionally does not provide arbitrary shell execution, silent app
installation, screen spying, or remote input injection. Remote actions are
allowlisted in both apps. See [docs/SECURITY.md](docs/SECURITY.md).

