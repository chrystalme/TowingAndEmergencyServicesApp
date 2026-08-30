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
      final provider = context.read<DriverProvider>();
      provider.loadProfile();
      provider.loadAssignments();
    });
  }

  Future<void> _respond(int dispatchId, String status) async {
    final provider = context.read<DriverProvider>();
    final ok = await provider.respond(dispatchId, status);
    if (!mounted) return;
    final accepted = status == 'accepted';
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(
        content: Text(ok
            ? (accepted
                ? 'Job accepted - you are enroute'
                : 'Job declined - back in the available pool')
            : provider.error ?? 'Could not respond'),
        backgroundColor: ok ? Colors.green : Colors.red,
      ));
  }

  /// A job card with the detail a driver needs to decide, plus the actions.
  /// Only `assigned` jobs are actionable; accepted ones stay visible so the
  /// driver can see what they are currently on.
  Widget _assignmentCard(Map<String, dynamic> job) {
    final isPending = job['status'] == 'assigned';
    final price = job['price'];
    final eta = job['eta_minutes'];
    final distance = job['distance_km'];
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isPending ? Colors.orange.shade300 : Colors.green.shade300,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  isPending ? Icons.notifications_active : Icons.local_shipping,
                  color: isPending ? Colors.orange.shade700 : Colors.green.shade700,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    (job['request_service_type'] ?? 'job').toString().toUpperCase(),
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                Text(
                  (job['status'] ?? '').toString(),
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(job['request_description']?.toString() ?? ''),
            const SizedBox(height: 6),
            Row(
              children: [
                Icon(Icons.place, size: 14, color: Colors.grey.shade600),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    job['request_location']?.toString() ?? '',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              children: [
                if (distance != null)
                  Text('$distance km', style: const TextStyle(fontSize: 12)),
                if (eta != null)
                  Text('~$eta min', style: const TextStyle(fontSize: 12)),
                if (price != null)
                  Text('Price $price',
                      style: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.bold)),
              ],
            ),
            if (isPending) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => _respond(job['id'] as int, 'declined'),
                      child: const Text('Decline'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => _respond(job['id'] as int, 'accepted'),
                      child: const Text('Accept'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
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

                // Assigned jobs. This half of the driver flow previously
                // existed only as a curl command in the README.
                Row(
                  children: [
                    const Text('Assigned Jobs',
                        style: TextStyle(
                            fontSize: 18, fontWeight: FontWeight.bold)),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.refresh),
                      tooltip: 'Refresh jobs',
                      onPressed: () => provider.loadAssignments(),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                if (provider.assignments.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text(
                      provider.isActive
                          ? 'No jobs yet. You are active and matchable.'
                          : 'Go active to start receiving jobs.',
                      style: TextStyle(color: Colors.grey.shade600),
                    ),
                  )
                else
                  ...provider.assignments.map(_assignmentCard),

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
