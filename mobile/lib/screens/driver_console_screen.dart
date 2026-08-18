import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/driver_provider.dart';
import '../widgets/primary_button.dart';

/// Driver Console — go active with your phone's location, or go offline.
///
/// Semantics (mirrors the web console + backend):
///   - **Active**: online + available + a phone position is published; the
///     dispatcher uses that position to match jobs to you.
///   - **Offline / busy**: you are not matchable and are shown as offline.
class DriverConsoleScreen extends StatefulWidget {
  const DriverConsoleScreen({super.key});

  @override
  State<DriverConsoleScreen> createState() => _DriverConsoleScreenState();
}

class _DriverConsoleScreenState extends State<DriverConsoleScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriverProvider>().loadProfile();
    });
  }

  Future<void> _goActive() async {
    final provider = context.read<DriverProvider>();
    await provider.goActive();
    if (mounted) {
      final message = provider.isActive
          ? 'You are now active — location shared for dispatch'
          : (provider.error ?? 'Could not go online');
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(message)));
    }
  }

  Future<void> _refreshPosition() async {
    final provider = context.read<DriverProvider>();
    await provider.refreshPosition();
    if (mounted) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text('Location refreshed')));
    }
  }

  Future<void> _goOffline() async {
    final provider = context.read<DriverProvider>();
    await provider.goOffline();
    if (mounted) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(const SnackBar(content: Text('You are now offline')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Driver Console'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: Consumer<DriverProvider>(
        builder: (context, provider, _) {
          if (provider.isLoading && !provider.hasPosition && !provider.isOnline) {
            return const Center(child: CircularProgressIndicator());
          }

          final active = provider.isActive;
          final busy = provider.isBusy;

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Status banner
                Card(
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(
                      color: active
                          ? Colors.green.shade300
                          : Colors.grey.shade300,
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              active
                                  ? Icons.wifi
                                  : busy
                                      ? Icons.local_shipping
                                      : Icons.wifi_off,
                              color: active
                                  ? Colors.green.shade700
                                  : busy
                                      ? Colors.orange.shade700
                                      : Colors.grey.shade500,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                active
                                    ? 'Active — available for dispatch'
                                    : busy
                                        ? 'Busy — handling a request'
                                        : 'Offline',
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          active
                              ? 'Your phone location is being used to route nearby jobs to you.'
                              : busy
                                  ? 'You will not receive new jobs until you finish this request.'
                                  : 'Go active to share your phone location and receive dispatch requests.',
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.grey.shade600,
                          ),
                        ),
                        if (provider.hasPosition && active) ...[
                          const SizedBox(height: 12),
                          Text(
                            'Location: ${provider.latitude!.toStringAsFixed(5)}, '
                            '${provider.longitude!.toStringAsFixed(5)}',
                            style: TextStyle(
                              fontSize: 13,
                              fontFamily: 'monospace',
                              color: Colors.grey.shade700,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                // Controls
                if (active)
                  Column(
                    children: [
                      SecondaryButton(
                        text: 'Refresh Location',
                        icon: Icons.my_location,
                        isLoading: provider.isLoading,
                        onPressed: _refreshPosition,
                      ),
                      const SizedBox(height: 12),
                      PrimaryButton(
                        text: 'Go Offline',
                        backgroundColor: Colors.red.shade600,
                        isLoading: provider.isLoading,
                        onPressed: _goOffline,
                      ),
                    ],
                  )
                else
                  Column(
                    children: [
                      PrimaryButton(
                        text: 'Go Active (share location)',
                        isLoading: provider.isLoading,
                        onPressed: _goActive,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Your phone GPS will be used as your dispatch location while active.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey.shade500,
                        ),
                      ),
                    ],
                  ),

                const SizedBox(height: 24),

                // Location capture note (simulated GPS, same as request screen)
                Card(
                  elevation: 0,
                  color: Colors.blue.shade50,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        Icon(Icons.info_outline, color: Colors.blue.shade700),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'This build captures a simulated phone location. '
                            'A real geolocator package replaces it in production.',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.blue.shade800,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
