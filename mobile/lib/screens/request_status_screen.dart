import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
import 'package:flutter_map/flutter_map.dart';
import '../providers/request_provider.dart';
import '../widgets/driver_contact_card.dart';
import '../utils/money.dart';
import '../services/tracking_service.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

/// Live view of one request after it has been filed.
///
/// Replaces the passive "dashboard waits for a snackbar" experience: the
/// user sits on a screen whose centre is a map, sees the assigned driver
/// move, and follows the job through [Requested → Accepted → En route →
/// Arrived → Completed]. The price shown is the price locked at dispatch.
class RequestStatusScreen extends StatefulWidget {
  const RequestStatusScreen({super.key, required this.requestId});

  final int requestId;

  @override
  State<RequestStatusScreen> createState() => _RequestStatusScreenState();
}

class _RequestStatusScreenState extends State<RequestStatusScreen> {
  Map<String, dynamic>? _request;
  bool _loading = true;
  bool _loadFailed = false;

  // Live driver position fed by the tracking socket.
  double? _driverLat;
  double? _driverLng;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _load();
      if (mounted) _watch();
    });
  }

  Future<void> _load() async {
    _loading = true;
    _loadFailed = false;
    if (mounted) setState(() {});
    // Captured before any await so the async gap never crosses a BuildContext.
    final provider = context.read<RequestProvider>();
    try {
      final request = (await apiService.getServiceRequest(widget.requestId))
          .cast<String, dynamic>();
      _request = request;
    } catch (_) {
      // The request list is our fallback source of truth (it is fetched
      // before this screen is ever reached, and it refreshes on pull).
      for (final r in provider.requests) {
        final row = (r as Map).cast<String, dynamic>();
        if (row['id'] == widget.requestId) {
          _request = row;
          break;
        }
      }
      _loadFailed = _request == null;
    } finally {
      _loading = false;
      if (mounted) setState(() {});
    }
  }

  /// Subscribe to live driver position + status events.
  void _watch() {
    if (_request == null) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      trackingService.watch(widget.requestId, onEvent: _onLiveEvent);
    });
  }

  void _onLiveEvent(Map<String, dynamic> event) {
    if (!mounted) return;
    final type = event['type'];
    if (type == 'driver_position') {
      final lat = event['lat'];
      final lng = event['lng'];
      if (lat is double && lng is double) {
        _driverLat = lat;
        _driverLng = lng;
        setState(() {});
      }
      return;
    }
    if (type == 'dispatch_status') {
      // Server is authoritative: re-read rather than patching local state.
      _load();
    }
  }

  @override
  void dispose() {
    trackingService.stop();
    super.dispose();
  }

  /// Which step of the journey is the job on?
  static int _stepIndex(Map<String, dynamic>? request) {
    if (request == null) return 0;
    final dispatch = request['dispatch_status'] as String?;
    switch (dispatch) {
      case 'arrived':
        return 4;
      case 'enroute':
        return 3;
      case 'accepted':
        return 2;
      case 'assigned':
        return 1;
    }
    final status = (request['status'] as String?) ?? 'pending';
    if (status == 'completed') return 5;
    if (status == 'cancelled') return -1;
    if (status == 'in_progress') return 4;
    return 0;
  }

  static final List<_StepDef> _steps = [
    _StepDef('Requested', Icons.circle),
    _StepDef('Accepted', Icons.check_circle_outline),
    _StepDef('En route', Icons.local_shipping),
    _StepDef('Arrived', Icons.directions_walk),
    _StepDef('Completed', Icons.check_circle),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Live Tracking'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            if (Navigator.of(context).canPop()) {
              context.pop();
            } else {
              context.go('/home');
            }
          },
        ),
      ),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _request == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_loadFailed) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 48, color: AppColors.danger),
            const SizedBox(height: 12),
            const Text('Could not load this request'),
            const SizedBox(height: 8),
            ElevatedButton(
              onPressed: () => context.go('/home'),
              child: const Text('Back to Home'),
            ),
          ],
        ),
      );
    }

    final request = _request!;
    final step = _stepIndex(request);
    final userLat = request['latitude'] as double?;
    final userLng = request['longitude'] as double?;
    final driverLat = _driverLat ?? request['driver_lat'] as double?;
    final driverLng = _driverLng ?? request['driver_lng'] as double?;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildStatusStrip(context, request, step),
          const SizedBox(height: 16),
          if (userLat != null && userLng != null)
            _buildMap(userLat, userLng, driverLat, driverLng),
          const SizedBox(height: 16),
          _buildPriceCard(context, request),
          const SizedBox(height: 8),
          DriverContactCard(request: request),
        ],
      ),
    );
  }

  Widget _buildStatusStrip(BuildContext context, Map<String, dynamic> request, int step) {
    if (step < 0) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Icon(Icons.cancel, color: AppColors.danger),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  'This request was cancelled',
                  style: TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              (request['description'] as String?) ?? 'Service request',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 14),
            for (var i = 0; i < _steps.length; i++)
              _buildStepRow(i, step),
          ],
        ),
      ),
    );
  }

  Widget _buildStepRow(int index, int step) {
    final def = _steps[index];
    final isDone = step >= index + 1;
    final isCurrent = step == index + 1;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: isDone
                  ? AppColors.successSoft
                  : isCurrent
                      ? AppColors.primarySoft
                      : Colors.grey.shade200,
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Icon(
                isDone ? Icons.check : def.icon,
                size: 16,
                color: isDone
                    ? AppColors.success
                    : isCurrent
                        ? AppColors.primary
                        : Colors.grey.shade500,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              def.label,
              style: TextStyle(
                fontSize: 14,
                fontWeight: isCurrent || isDone ? FontWeight.w600 : FontWeight.w400,
                color: isCurrent
                    ? AppColors.primary
                    : isDone
                        ? AppColors.success
                        : Colors.grey.shade600,
              ),
            ),
          ),
          if (isCurrent)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: AppColors.primarySoft,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Current',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: AppColors.primary,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildMap(
    double userLat,
    double userLng,
    double? driverLat,
    double? driverLng,
  ) {
    final markers = <Marker>[
      Marker(
        point: LatLng(userLat, userLng),
        child: _mapPin(
          color: AppColors.primary,
          icon: Icons.person_pin_circle,
        ),
      ),
    ];
    if (driverLat != null && driverLng != null) {
      markers.add(Marker(
        point: LatLng(driverLat, driverLng),
        child: _mapPin(color: AppColors.primaryDark, icon: Icons.local_shipping),
      ));
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(AppRadii.md),
      child: AspectRatio(
        aspectRatio: 16 / 10,
        child: FlutterMap(
          options: MapOptions(
            initialCenter: LatLng(userLat, userLng),
            initialZoom: 14,
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            ),
            MarkerLayer(markers: markers),
          ],
        ),
      ),
    );
  }

  Widget _mapPin({required Color color, required IconData icon}) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 3),
      ),
      child: Center(child: Icon(icon, color: Colors.white, size: 18)),
    );
  }

  Widget _buildPriceCard(BuildContext context, Map<String, dynamic> request) {
    final price = request['price'];
    final distance = request['distance_km'];
    final eta = request['eta_minutes'];
    final driver = request['driver_email'] as String?;
    if (price == null && distance == null && eta == null && driver == null) {
      return const SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.receipt, size: 18, color: AppColors.primary),
                const SizedBox(width: 8),
                const Text(
                  'Quote',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                ),
              ],
            ),
            const SizedBox(height: 10),
            ..._buildQuoteRows(price, distance, eta, driver),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildQuoteRows(
    Object? price,
    Object? distance,
    Object? eta,
    String? driver,
  ) {
    final rows = <Widget>[];
    void add(String label, String value) {
      rows.add(Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
        ],
      ));
    }

    if (price != null) add('Estimated price', formatMoney(price, 'NGN'));
    if (distance != null) add('Distance', '$distance km');
    if (eta != null) add('ETA', '~$eta min');
    if (driver != null) add('Driver', driver);
    if (rows.isEmpty) {
      rows.add(Text(
        'Waiting for a driver to be matched…',
        style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
      ));
    }
    return rows;
  }
}

class _StepDef {
  const _StepDef(this.label, this.icon);
  final String label;
  final IconData icon;
}