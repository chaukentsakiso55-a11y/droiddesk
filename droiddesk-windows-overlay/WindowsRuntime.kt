package com.orailnoor.droiddesk.runtime

import android.content.Context
import android.util.Log
import java.io.File
import java.util.Properties

class WindowsRuntime(private val context: Context) {
    companion object {
        private const val TAG = "WindowsRuntime"
        @Volatile private var sessionProcess: Process? = null
        @Volatile private var tpmProcess: Process? = null
    }

    private val linuxRuntime = LinuxRuntime(context)
    private val prefixDir = File(context.filesDir, "usr")
    private val binDir = File(prefixDir, "bin")
    private val shareQemuDir = File(prefixDir, "share/qemu")
    private val vmDir = File(context.filesDir, "windows-vm")
    private val diskFile = File(vmDir, "windows.qcow2")
    private val isoFile = File(vmDir, "windows-install.iso")
    private val varsFile = File(vmDir, "windows-vars.fd")
    private val configFile = File(vmDir, "vm.properties")
    private val tpmDir = File(vmDir, "tpm")
    private val tpmSocket = File(vmDir, "swtpm.sock")

    fun status(): Map<String, Any> {
        val qemu = File(binDir, "qemu-system-x86_64")
        val qemuImg = File(binDir, "qemu-img")
        val firmware = findFirmwareCode()
        val props = readProperties()
        return mapOf(
            "prepared" to (qemu.isFile && qemuImg.isFile && firmware != null),
            "qemuAvailable" to qemu.isFile,
            "uefiAvailable" to (firmware != null),
            "tpmAvailable" to File(binDir, "swtpm").isFile,
            "diskExists" to diskFile.isFile,
            "diskSizeGb" to (props.getProperty("diskSizeGb")?.toIntOrNull() ?: 0),
            "diskFileSizeMb" to if (diskFile.isFile) diskFile.length() / (1024L * 1024L) else 0L,
            "isoExists" to isoFile.isFile,
            "isoFileSizeMb" to if (isoFile.isFile) isoFile.length() / (1024L * 1024L) else 0L,
            "running" to isRunning(),
            "vmPath" to vmDir.absolutePath,
        )
    }

    fun prepareRuntime(onProgress: (Double, String) -> Unit): Boolean {
        vmDir.mkdirs()
        val qemu = File(binDir, "qemu-system-x86_64")
        val qemuImg = File(binDir, "qemu-img")

        if (qemu.isFile && qemuImg.isFile && findFirmwareCode() != null) {
            onProgress(1.0, "Windows virtualization runtime is ready")
            ensureUefiVars()
            return true
        }

        return try {
            onProgress(0.04, "Preparing DroidDesk userspace...")
            linuxRuntime.extractBootstrapIfNeeded(context)
            linuxRuntime.setupBootstrap()
            if (!linuxRuntime.isBootstrapped()) {
                onProgress(-1.0, "DroidDesk userspace could not be prepared")
                return false
            }

            onProgress(0.18, "Enabling the Termux X11 package repository...")
            if (!linuxRuntime.installRepoPackages()) {
                onProgress(-1.0, "Could not configure the X11 package repository")
                return false
            }

            onProgress(0.38, "Installing QEMU x86-64, disk tools and TPM support...")
            if (!linuxRuntime.installPackageGroup(
                    "pkg install -y qemu-system-x86-64 qemu-utils swtpm pulseaudio"
                )
            ) {
                onProgress(-1.0, "QEMU package installation failed")
                return false
            }

            onProgress(0.88, "Checking UEFI firmware...")
            val ok = qemu.isFile && qemuImg.isFile && findFirmwareCode() != null
            if (!ok) {
                onProgress(-1.0, "QEMU installed but its emulator or UEFI firmware is missing")
                return false
            }

            ensureUefiVars()
            onProgress(1.0, "Windows virtualization runtime is ready")
            true
        } catch (error: Throwable) {
            Log.e(TAG, "Windows runtime preparation failed", error)
            onProgress(-1.0, "Runtime setup failed: ${error.message ?: error.javaClass.simpleName}")
            false
        }
    }

    fun importIso(sourcePath: String, onProgress: (Double, String) -> Unit): Boolean {
        val source = File(sourcePath)
        if (!source.isFile) {
            onProgress(-1.0, "Selected ISO could not be opened")
            return false
        }

        vmDir.mkdirs()
        val partial = File(vmDir, "windows-install.iso.part")
        partial.delete()

        return try {
            val total = source.length().coerceAtLeast(1L)
            var copied = 0L
            source.inputStream().buffered().use { input ->
                partial.outputStream().buffered().use { output ->
                    val buffer = ByteArray(1024 * 1024)
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        output.write(buffer, 0, read)
                        copied += read
                        val progress = (copied.toDouble() / total.toDouble()).coerceIn(0.0, 1.0)
                        onProgress(progress, "Copying Windows ISO… ${copied / (1024 * 1024)} / ${total / (1024 * 1024)} MB")
                    }
                }
            }
            if (isoFile.exists()) isoFile.delete()
            check(partial.renameTo(isoFile)) { "Could not finalize ISO copy" }
            onProgress(1.0, "Windows ISO imported")
            true
        } catch (error: Throwable) {
            partial.delete()
            Log.e(TAG, "ISO import failed", error)
            onProgress(-1.0, "ISO import failed: ${error.message ?: "unknown error"}")
            false
        }
    }

    fun removeIso(): Boolean {
        if (isRunning()) return false
        return !isoFile.exists() || isoFile.delete()
    }

    fun createDisk(sizeGb: Int, onProgress: (Double, String) -> Unit): Boolean {
        val safeSize = sizeGb.coerceIn(24, 256)
        val qemuImg = File(binDir, "qemu-img")
        if (!qemuImg.isFile) {
            onProgress(-1.0, "Prepare the Windows runtime first")
            return false
        }
        if (isRunning()) {
            onProgress(-1.0, "Stop Windows before changing the virtual disk")
            return false
        }

        vmDir.mkdirs()
        val tempDisk = File(vmDir, "windows-new.qcow2")
        tempDisk.delete()
        onProgress(0.2, "Creating a sparse ${safeSize} GB QCOW2 disk…")

        val result = runNative(
            listOf(
                qemuImg.absolutePath,
                "create",
                "-f",
                "qcow2",
                tempDisk.absolutePath,
                "${safeSize}G",
            )
        )
        if (result.first != 0 || !tempDisk.isFile) {
            tempDisk.delete()
            onProgress(-1.0, "Virtual disk creation failed: ${result.second.takeLast(500)}")
            return false
        }

        if (diskFile.exists()) diskFile.delete()
        if (!tempDisk.renameTo(diskFile)) {
            tempDisk.delete()
            onProgress(-1.0, "Could not finalize virtual disk")
            return false
        }

        val props = readProperties()
        props.setProperty("diskSizeGb", safeSize.toString())
        writeProperties(props)
        onProgress(1.0, "Virtual disk ready")
        return true
    }

    fun saveLaunchConfig(ramMb: Int, cpuCount: Int, bootInstaller: Boolean) {
        vmDir.mkdirs()
        val props = readProperties()
        props.setProperty("ramMb", ramMb.coerceIn(1024, 6144).toString())
        props.setProperty("cpuCount", cpuCount.coerceIn(1, 4).toString())
        props.setProperty("bootInstaller", bootInstaller.toString())
        writeProperties(props)
    }

    fun startSession() {
        if (isRunning()) return
        val qemu = File(binDir, "qemu-system-x86_64")
        check(qemu.isFile) { "QEMU is not installed" }
        check(diskFile.isFile) { "Windows virtual disk is missing" }

        val firmwareCode = checkNotNull(findFirmwareCode()) { "UEFI firmware is missing" }
        ensureUefiVars()
        check(varsFile.isFile) { "UEFI variable store could not be created" }

        val props = readProperties()
        val ramMb = (props.getProperty("ramMb")?.toIntOrNull() ?: 2048).coerceIn(1024, 6144)
        val cpuCount = (props.getProperty("cpuCount")?.toIntOrNull() ?: 2).coerceIn(1, 4)
        val bootInstaller = props.getProperty("bootInstaller")?.toBooleanStrictOrNull() ?: true

        linuxRuntime.executeCommand("pulseaudio --start --exit-idle-time=-1 >/dev/null 2>&1 || true")

        val args = mutableListOf(
            qemu.absolutePath,
            "-name", "DroidDesk Windows",
            "-machine", "pc,vmport=off",
            "-accel", "tcg,thread=multi",
            "-cpu", "max",
            "-smp", "cpus=$cpuCount",
            "-m", ramMb.toString(),
            "-rtc", "base=localtime,clock=host",
            "-drive", "if=pflash,format=raw,readonly=on,file=${firmwareCode.absolutePath}",
            "-drive", "if=pflash,format=raw,file=${varsFile.absolutePath}",
            "-drive", "file=${diskFile.absolutePath},if=ide,index=0,media=disk,format=qcow2",
            "-netdev", "user,id=net0",
            "-device", "e1000,netdev=net0",
            "-device", "qemu-xhci,id=xhci",
            "-device", "usb-tablet,bus=xhci.0",
            "-vga", "std",
            "-audiodev", "pa,id=audio0",
            "-device", "ich9-intel-hda",
            "-device", "hda-duplex,audiodev=audio0",
            "-display", "sdl,gl=off",
        )

        if (bootInstaller && isoFile.isFile) {
            args += listOf("-cdrom", isoFile.absolutePath, "-boot", "order=d,menu=on")
        } else {
            args += listOf("-boot", "order=c,menu=on")
        }

        startTpm()?.let { socket ->
            args += listOf(
                "-chardev", "socket,id=chrtpm,path=${socket.absolutePath}",
                "-tpmdev", "emulator,id=tpm0,chardev=chrtpm",
                "-device", "tpm-tis,tpmdev=tpm0",
            )
        }

        val process = ProcessBuilder(args)
            .directory(vmDir)
            .redirectErrorStream(true)
            .also { pb ->
                pb.environment().clear()
                pb.environment().putAll(linuxRuntime.getTermuxEnv())
                pb.environment()["DISPLAY"] = ":0"
                pb.environment()["QEMU_AUDIO_DRV"] = "pa"
            }
            .start()
        sessionProcess = process

        Thread({
            try {
                process.inputStream.bufferedReader().forEachLine { line ->
                    Log.d(TAG, "QEMU: $line")
                }
            } catch (_: Throwable) {
            } finally {
                sessionProcess = null
                stopTpm()
            }
        }, "DroidDesk-Windows-QEMU").start()
    }

    fun stopSession() {
        sessionProcess?.let { process ->
            runCatching {
                process.destroy()
                if (!process.waitFor(1500, java.util.concurrent.TimeUnit.MILLISECONDS)) {
                    process.destroyForcibly()
                }
            }
        }
        sessionProcess = null
        stopTpm()
    }

    fun isRunning(): Boolean = sessionProcess?.isAlive == true

    private fun startTpm(): File? {
        val swtpm = File(binDir, "swtpm")
        if (!swtpm.isFile) return null

        stopTpm()
        vmDir.mkdirs()
        tpmDir.mkdirs()
        tpmSocket.delete()

        return try {
            val process = ProcessBuilder(
                swtpm.absolutePath,
                "socket",
                "--tpm2",
                "--tpmstate", "dir=${tpmDir.absolutePath}",
                "--ctrl", "type=unixio,path=${tpmSocket.absolutePath}",
                "--flags", "not-need-init",
            ).redirectErrorStream(true).also { pb ->
                pb.environment().clear()
                pb.environment().putAll(linuxRuntime.getTermuxEnv())
            }.start()
            tpmProcess = process

            val deadline = System.currentTimeMillis() + 2500
            while (!tpmSocket.exists() && process.isAlive && System.currentTimeMillis() < deadline) {
                Thread.sleep(25)
            }
            if (tpmSocket.exists() && process.isAlive) tpmSocket else {
                process.destroyForcibly()
                tpmProcess = null
                null
            }
        } catch (error: Throwable) {
            Log.w(TAG, "TPM emulator unavailable: ${error.message}")
            tpmProcess = null
            null
        }
    }

    private fun stopTpm() {
        tpmProcess?.destroyForcibly()
        tpmProcess = null
        tpmSocket.delete()
    }

    private fun findFirmwareCode(): File? {
        val candidates = listOf(
            File(shareQemuDir, "edk2-x86_64-code.fd"),
            File(shareQemuDir, "edk2-x86_64-secure-code.fd"),
        )
        return candidates.firstOrNull { it.isFile }
    }

    private fun findFirmwareVarsTemplate(): File? {
        val candidates = listOf(
            File(shareQemuDir, "edk2-i386-vars.fd"),
            File(shareQemuDir, "edk2-x86_64-vars.fd"),
        )
        return candidates.firstOrNull { it.isFile }
    }

    private fun ensureUefiVars() {
        if (varsFile.isFile) return
        vmDir.mkdirs()
        val template = findFirmwareVarsTemplate() ?: return
        template.copyTo(varsFile, overwrite = true)
    }

    private fun runNative(command: List<String>): Pair<Int, String> {
        return try {
            val process = ProcessBuilder(command)
                .directory(vmDir.apply { mkdirs() })
                .redirectErrorStream(true)
                .also { pb ->
                    pb.environment().clear()
                    pb.environment().putAll(linuxRuntime.getTermuxEnv())
                }
                .start()
            val output = process.inputStream.bufferedReader().readText()
            val code = process.waitFor()
            code to output
        } catch (error: Throwable) {
            -1 to (error.message ?: error.javaClass.simpleName)
        }
    }

    private fun readProperties(): Properties {
        val props = Properties()
        if (configFile.isFile) {
            runCatching { configFile.inputStream().use(props::load) }
        }
        return props
    }

    private fun writeProperties(props: Properties) {
        vmDir.mkdirs()
        configFile.outputStream().use { props.store(it, "DroidDesk Windows VM") }
    }
}
