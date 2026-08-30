import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../providers/request_provider.dart';
import '../widgets/primary_button.dart';
import '../widgets/stat_card.dart';
import '../services/tracking_service.dart';
import '../widgets/driver_contact_card.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  /// The request currently being watched over the socket, if any.
  int? _watching;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await context.read<RequestProvider>().fetchRequests();
      if (mounted) _watchActiveRequest();
    });
  }

  @override
  void dispose() {
    trackingService.stop();
    super.dispose();
  }

  /// Subscribe to the newest request that is still in flight.
  ///
  /// Without this the client filed a request and then learned nothing: their
  /// tow could accept, drive over, arrive and finish while the screen still
  /// said 'pending'. The only way to find out was to reopen the app.
  void _watchActiveRequest() {
    final requests = context.read<RequestProvider>().requests;
    Map<String, dynamic>? active;
    for (final r in requests) {
      final row = (r as Map).cast<String, dynamic>();
      final status = row['status'] as String?;
      if (status != 'completed' && status != 'cancelled') {
        active = row;
        break;
      }
    }

    if (active == null) {
      trackingService.stop();
      _watching = null;
      return;
    }

    final id = active['id'] as int;
    if (_watching == id) return;
    _watching = id;
    trackingService.watch(id, onEvent: _onLiveEvent);
  }

  void _onLiveEvent(Map<String, dynamic> event) {
    if (!mounted) return;
    if (event['type'] != 'dispatch_status') return;

    // Re-read rather than patching local state: the server is the authority
    // on what a status transition did to the request.
    context.read<RequestProvider>().fetchRequests();

    final status = (event['status'] ?? '').toString();
    final message = _statusMessage(status, event['driver_email'] as String?);
    if (message == null) return;

    final done = status == 'completed';
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(
        content: Row(
          children: [
            Icon(done ? Icons.check_circle : Icons.local_shipping,
                color: Colors.white),
            const SizedBox(width: 12),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: done ? Colors.green.shade700 : Colors.indigo,
        duration: const Duration(seconds: 6),
      ));

    if (done) {
      // Nothing left in flight on this request; release the socket.
      trackingService.stop();
      _watching = null;
    }
  }

  static String? _statusMessage(String status, String? driver) {
    final who = driver ?? 'Your driver';
    switch (status) {
      case 'assigned':
        return '$who has been dispatched to you';
      case 'accepted':
        return '$who accepted your request';
      case 'enroute':
        return '$who is on the way';
      case 'arrived':
        return '$who has arrived';
      case 'completed':
        return 'Your request is complete';
      case 'cancelled':
        return 'Your request was cancelled';
      case 'declined':
        return 'Finding you another driver…';
      default:
        return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        actions: [
          Consumer<AuthProvider>(
            builder: (context, auth, _) {
              return IconButton(
                icon: const Icon(Icons.logout),
                onPressed: () async {
                  await auth.logout();
                  if (context.mounted) {
                    context.go('/login');
                  }
                },
              );
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => context.read<RequestProvider>().fetchRequests(),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Stats cards
              Consumer<RequestProvider>(
                builder: (context, provider, _) {
                  final total = provider.requests.length;
                  final pending = provider.requests.where((r) => r['status'] == 'pending').length;

                  return Row(
                    children: [
                      Expanded(
                        child: StatCard(
                          title: 'Total',
                          value: total.toString(),
                          icon: Icons.list_alt,
                          color: const Color(0xFF1D4ED8),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: StatCard(
                          title: 'Pending',
                          value: pending.toString(),
                          icon: Icons.pending_actions,
                          color: Colors.orange,
                        ),
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(height: 12),
              Consumer<RequestProvider>(
                builder: (context, provider, _) {
                  final inProgress = provider.requests.where((r) => r['status'] == 'in_progress').length;
                  final completed = provider.requests.where((r) => r['status'] == 'completed').length;

                  return Row(
                    children: [
                      Expanded(
                        child: StatCard(
                          title: 'In Progress',
                          value: inProgress.toString(),
                          icon: Icons.local_shipping,
                          color: Colors.blue,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: StatCard(
                          title: 'Completed',
                          value: completed.toString(),
                          icon: Icons.check_circle,
                          color: Colors.green,
                        ),
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(height: 24),

              // Request Service button
              PrimaryButton(
                text: 'Request Service',
                onPressed: () => context.push('/request'),
              ),
              const SizedBox(height: 12),
              // Driver Console, only for approved drivers. The server
              // refuses the endpoints outright; this stops offering a
              // button that could only produce a 403.
              if (context.watch<AuthProvider>().canDrive)
              // Driver Console button — go active as a driver or go offline
              SecondaryButton(
                text: 'Driver Console',
                icon: Icons.local_shipping,
                onPressed: () => context.push('/driver'),
              ),
              const SizedBox(height: 24),

              // Recent Requests
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Recent Requests',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: const Color(0xFF111827),
                    ),
                  ),
                  TextButton(
                    onPressed: () => context.push('/requests'),
                    child: const Text('View All'),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              // Requests list
              Consumer<RequestProvider>(
                builder: (context, provider, _) {
                  if (provider.isLoading && provider.requests.isEmpty) {
                    return const Center(
                      child: Padding(
                        padding: EdgeInsets.all(32),
                        child: CircularProgressIndicator(),
                      ),
                    );
                  }

                  if (provider.requests.isEmpty) {
                    return Card(
                      child: Padding(
                        padding: const EdgeInsets.all(32),
                        child: Column(
                          children: [
                            Icon(Icons.inbox_outlined, size: 48, color: Colors.grey.shade400),
                            const SizedBox(height: 16),
                            Text(
                              'No service requests yet',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                color: Colors.grey.shade600,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Tap "Request Service" to get help',
                              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                color: Colors.grey.shade500,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  }

                  return ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: provider.requests.length > 5 ? 5 : provider.requests.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final request = provider.requests[index];
                      return _buildRequestCard(context, request);
                    },
                  );
                },
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/request'),
        icon: const Icon(Icons.add),
        label: const Text('Request'),
        backgroundColor: const Color(0xFF1D4ED8),
        foregroundColor: Colors.white,
      ),
    );
  }

  Widget _buildRequestCard(BuildContext context, Map<String, dynamic> request) {
    final status = request['status'] as String? ?? 'pending';
    Color statusColor;
    IconData statusIcon;
    
    switch (status) {
      case 'pending':
        statusColor = Colors.orange;
        statusIcon = Icons.pending;
        break;
      case 'in_progress':
        statusColor = Colors.blue;
        statusIcon = Icons.local_shipping;
        break;
      case 'completed':
        statusColor = Colors.green;
        statusIcon = Icons.check_circle;
        break;
      default:
        statusColor = Colors.grey;
        statusIcon = Icons.help;
    }

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        leading: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: const Color(0xFF1D4ED8).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(Icons.local_shipping, color: Color(0xFF1D4ED8), size: 24),
        ),
        title: Text(
          request['description'] as String? ?? 'Service Request',
          style: const TextStyle(
            fontWeight: FontWeight.w600,
            color: Color(0xFF111827),
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(Icons.location_on_outlined, size: 14, color: Colors.grey.shade500),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    request['location'] as String? ?? '',
                    style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            // Only rendered once the driver has accepted; the API withholds
            // these fields until then.
            DriverContactCard(request: request),
          ],
        ),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: statusColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(statusIcon, size: 14, color: statusColor),
              const SizedBox(width: 4),
              Text(
                status.replaceAll('_', ' ').toUpperCase(),
                style: TextStyle(
                  color: statusColor,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
        onTap: () {
          // Navigate to detail (not implemented yet)
        },
      ),
    );
  }
}