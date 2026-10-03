import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:droiddesk/services/platform_bridge.dart';
import 'package:droiddesk/theme/droid_theme.dart';

class WindowsScreen extends StatefulWidget {
  const WindowsScreen({super.key});

  @override
  State<WindowsScreen> createState() => _WindowsScreenState();
}

class _WindowsScreenState extends State<WindowsScreen> {
  Map<String, dynamic> _status = const {};
  bool _busy = false;
  double _progress = 0;
  String _progressText = '';
  int _diskGb = 64;
  int _ramMb = 2048;
  int _cpuCount = 2;
  bool _bootInstaller = true;

  @override
  void initState() {
    super.initState();
    DroidDeskPlatform.onWindowsProgress = (progress, status) {
      if (!mounted) return;
      setState(() {
        _progress = progress.clamp(0.0, 1.0);
        _progressText = status;
      });
    };
    _refresh();
  }

  @override
  void dispose() {
    DroidDeskPlatform.onWindowsProgress = null;
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final status = await DroidDeskPlatform.getWindowsStatus();
      if (!mounted) return;
      setState(() => _status = status);
    } catch (_) {}
  }

  Future<void> _run(Future<bool> Function() action) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _progress = 0;
      _progressText = 'Working…';
    });
    try {
      final ok = await action();
      await _refresh();
      if (!mounted) return;
      if (!ok) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _progressText.isEmpty ? 'Operation failed' : _progressText,
            ),
            backgroundColor: DroidTheme.error,
          ),
        );
      }
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.toString()),
          backgroundColor: DroidTheme.error,
        ),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickIso() async {
    if (_busy) return;
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['iso'],
      allowMultiple: false,
      withData: false,
    );
    final path = result?.files.single.path;
    if (path == null) return;
    await _run(() => DroidDeskPlatform.importWindowsIso(path));
  }

  Future<void> _startWindows() async {
    if (_status['prepared'] != true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Prepare the Windows runtime first.')),
      );
      return;
    }
    if (_status['diskExists'] != true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Create a virtual disk first.')),
      );
      return;
    }
    if (_bootInstaller && _status['isoExists'] != true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Import a Windows ISO first.')),
      );
      return;
    }

    final ok = await DroidDeskPlatform.startWindows(
      ramMb: _ramMb,
      cpuCount: _cpuCount,
      bootInstaller: _bootInstaller,
    );
    await _refresh();
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Windows could not start. Check the VM setup.'),
          backgroundColor: DroidTheme.error,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final prepared = _status['prepared'] == true;
    final diskExists = _status['diskExists'] == true;
    final isoExists = _status['isoExists'] == true;
    final running = _status['running'] == true;

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: DroidTheme.backgroundGradient),
        child: SafeArea(
          child: RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 28),
              children: [
                Row(
                  children: [
                    Container(
                      width: 46,
                      height: 46,
                      decoration: BoxDecoration(
                        gradient: DroidTheme.primaryGradient,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: const Icon(Icons.window_rounded, color: Colors.white),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Windows 10 / 11', style: DroidTheme.headingLg),
                          Text(
                            running ? 'Virtual PC running' : 'QEMU virtual PC on Android',
                            style: DroidTheme.bodySm.copyWith(
                              color: running
                                  ? DroidTheme.accent
                                  : DroidTheme.textMuted,
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      onPressed: _busy ? null : _refresh,
                      icon: const Icon(Icons.refresh_rounded),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                _panel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('VM STATUS', style: DroidTheme.label),
                      const SizedBox(height: 12),
                      _statusRow('QEMU', prepared ? 'READY' : 'NOT READY', prepared),
                      _statusRow('UEFI', _status['uefiAvailable'] == true ? 'READY' : 'MISSING', _status['uefiAvailable'] == true),
                      _statusRow('TPM 2.0', _status['tpmAvailable'] == true ? 'AVAILABLE' : 'OPTIONAL', _status['tpmAvailable'] == true),
                      _statusRow(
                        'Virtual disk',
                        diskExists
                            ? '${_status['diskSizeGb'] ?? '?'} GB QCOW2'
                            : 'NOT CREATED',
                        diskExists,
                      ),
                      _statusRow(
                        'Installer ISO',
                        isoExists
                            ? '${_status['isoFileSizeMb'] ?? '?'} MB'
                            : 'NOT IMPORTED',
                        isoExists,
                      ),
                    ],
                  ),
                ),
                if (_busy || _progressText.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _panel(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_progressText, style: DroidTheme.bodyMd),
                        const SizedBox(height: 10),
                        LinearProgressIndicator(
                          value: _busy && _progress == 0 ? null : _progress,
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                Text('SETUP', style: DroidTheme.label),
                const SizedBox(height: 10),
                _action(
                  icon: Icons.memory_rounded,
                  title: prepared ? 'Runtime ready' : 'Prepare Windows runtime',
                  subtitle: prepared
                      ? 'QEMU, UEFI and disk tools are installed'
                      : 'Installs the x86-64 emulator and VM tools inside DroidDesk',
                  onTap: _busy || prepared
                      ? null
                      : () => _run(DroidDeskPlatform.prepareWindowsRuntime),
                ),
                const SizedBox(height: 10),
                _action(
                  icon: Icons.album_rounded,
                  title: isoExists ? 'Replace Windows ISO' : 'Import Windows ISO',
                  subtitle: 'Choose a Windows 10 or Windows 11 .iso from your phone',
                  onTap: _busy ? null : _pickIso,
                ),
                const SizedBox(height: 10),
                _panel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('VIRTUAL STORAGE', style: DroidTheme.label),
                      const SizedBox(height: 10),
                      Text(
                        'QCOW2 grows as Windows uses space, so a 64 GB virtual disk does not reserve 64 GB immediately.',
                        style: DroidTheme.bodySm,
                      ),
                      const SizedBox(height: 14),
                      DropdownButtonFormField<int>(
                        initialValue: _diskGb,
                        decoration: const InputDecoration(
                          labelText: 'Maximum virtual disk size',
                          border: OutlineInputBorder(),
                        ),
                        items: const [32, 48, 64, 96, 128]
                            .map(
                              (value) => DropdownMenuItem(
                                value: value,
                                child: Text('$value GB'),
                              ),
                            )
                            .toList(),
                        onChanged: _busy
                            ? null
                            : (value) => setState(() => _diskGb = value ?? 64),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: _busy
                              ? null
                              : () => _confirmCreateDisk(diskExists),
                          icon: const Icon(Icons.storage_rounded),
                          label: Text(
                            diskExists ? 'Recreate virtual disk' : 'Create virtual disk',
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Text('PERFORMANCE', style: DroidTheme.label),
                const SizedBox(height: 10),
                _panel(
                  child: Column(
                    children: [
                      DropdownButtonFormField<int>(
                        initialValue: _ramMb,
                        decoration: const InputDecoration(
                          labelText: 'VM memory',
                          border: OutlineInputBorder(),
                        ),
                        items: const [1536, 2048, 3072, 4096]
                            .map(
                              (value) => DropdownMenuItem(
                                value: value,
                                child: Text(
                                  value >= 1024
                                      ? '${(value / 1024).toStringAsFixed(value % 1024 == 0 ? 0 : 1)} GB RAM'
                                      : '$value MB RAM',
                                ),
                              ),
                            )
                            .toList(),
                        onChanged: running
                            ? null
                            : (value) => setState(() => _ramMb = value ?? 2048),
                      ),
                      const SizedBox(height: 12),
                      DropdownButtonFormField<int>(
                        initialValue: _cpuCount,
                        decoration: const InputDecoration(
                          labelText: 'Virtual CPU cores',
                          border: OutlineInputBorder(),
                        ),
                        items: const [1, 2, 3, 4]
                            .map(
                              (value) => DropdownMenuItem(
                                value: value,
                                child: Text('$value core${value == 1 ? '' : 's'}'),
                              ),
                            )
                            .toList(),
                        onChanged: running
                            ? null
                            : (value) => setState(() => _cpuCount = value ?? 2),
                      ),
                      const SizedBox(height: 8),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        value: _bootInstaller,
                        onChanged: running
                            ? null
                            : (value) => setState(() => _bootInstaller = value),
                        title: const Text('Boot from installer ISO'),
                        subtitle: const Text(
                          'Turn this off after Windows is installed to boot from the virtual disk.',
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 54,
                  child: ElevatedButton.icon(
                    onPressed: _busy
                        ? null
                        : running
                            ? () => _run(DroidDeskPlatform.stopWindows)
                            : _startWindows,
                    icon: Icon(
                      running ? Icons.stop_circle_rounded : Icons.play_arrow_rounded,
                    ),
                    label: Text(running ? 'Stop Windows' : 'Start Windows'),
                    style: running
                        ? ElevatedButton.styleFrom(
                            backgroundColor: DroidTheme.error,
                            foregroundColor: Colors.white,
                          )
                        : null,
                  ),
                ),
                const SizedBox(height: 14),
                _panel(
                  child: Text(
                    'This uses full-system x86-64 emulation, not a fake Windows theme. It can install normal Windows .exe apps inside the VM, but it will be much slower than native Linux on ARM. Windows itself and its license are not bundled.',
                    style: DroidTheme.bodySm,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _confirmCreateDisk(bool replacing) async {
    if (replacing) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Recreate virtual disk?'),
          content: const Text(
            'This deletes the current Windows virtual disk and everything installed inside it.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Recreate'),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
    }
    await _run(() => DroidDeskPlatform.createWindowsDisk(_diskGb));
  }

  Widget _statusRow(String label, String value, bool ok) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Expanded(child: Text(label, style: DroidTheme.bodyMd)),
          Text(
            value,
            style: DroidTheme.monoSm.copyWith(
              color: ok ? DroidTheme.accent : DroidTheme.textMuted,
            ),
          ),
        ],
      ),
    );
  }

  Widget _panel({required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: DroidTheme.cardBg,
        borderRadius: BorderRadius.circular(DroidTheme.radiusMd),
        border: Border.all(color: DroidTheme.surfaceBorder),
      ),
      child: child,
    );
  }

  Widget _action({
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback? onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(DroidTheme.radiusMd),
      child: _panel(
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: DroidTheme.primary.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: DroidTheme.primaryLight),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: DroidTheme.headingSm),
                  const SizedBox(height: 3),
                  Text(subtitle, style: DroidTheme.bodySm),
                ],
              ),
            ),
            const Icon(Icons.chevron_right_rounded, color: DroidTheme.textMuted),
          ],
        ),
      ),
    );
  }
}
