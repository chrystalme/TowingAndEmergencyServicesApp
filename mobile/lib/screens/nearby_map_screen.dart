import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';

import '../providers/nearby_provider.dart';
import '../services/location_service.dart';
import '../widgets/driver_marker.dart';
import '../widgets/driver_bottom_sheet.dart';
import '../models/driver_candidate.dart';
import '../theme/app_theme.dart';

/// The commute-map tab: the whole screen is a map.
///
/// The blue pin is where the caller is; the tow-truck markers are available
/// drivers near them, ranked by the server by distance with an upfront fare.
/// Tapping a driver opens the bottom sheet; "Request service" takes the user
/// into the (single-screen) request flow. A service-type selector re-quotes
/// every marker against a different rate.
class NearbyMapScreen extends StatefulWidget {
  const NearbyMapScreen({super.key});

  @override
  State<NearbyMapScreen> createState() => _NearbyMapScreenState();
}

class _NearbyMapScreenState extends State<NearbyMapScreen> {
  static const _services = <(String, String)>[
    ('towing', 'Towing'),
    ('roadside', 'Roadside'),
    ('recovery', 'Recovery'),
  ];

  final MapController _mapController = MapController();
  LatLng? _origin;
  String? _locationError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final provider = context.read<NearbyProvider>();
      provider.setVisible(true);
      await _ensureOrigin();
      if (mounted && _origin != null) {
        provider.select(null);
        provider.refresh(lat: _origin!.latitude, lng: _origin!.longitude);
      }
    });
  }

  @override
  void dispose() {
    context.read<NearbyProvider>().setVisible(false);
    super.dispose();
  }

  Future<void> _ensureOrigin() async {
    if (_origin != null) return;
    try {
      final position = await locationService.current();
      _origin = LatLng(position.latitude, position.longitude);
      _locationError = null;
      if (mounted) {
        _mapController.move(_origin!, 15);
        setState(() {});
      }
    } on LocationException catch (e) {
      _locationError = e.message;
      if (mounted) setState(() {});
    } catch (e) {
      _locationError = 'Could not get your location: $e';
      if (mounted) setState(() {});
    }
  }

  Future<void> _retryLocation(BuildContext context) async {
    final provider = context.read<NearbyProvider>();
    _origin = null;
    setState(() {});
    await _ensureOrigin();
    if (mounted && _origin != null) {
      provider.refresh(lat: _origin!.latitude, lng: _origin!.longitude);
    }
  }

  void _onServiceChanged(BuildContext context, String serviceType, String label) {
    final provider = context.read<NearbyProvider>();
    provider.serviceType = serviceType;
    provider.refresh(lat: _origin?.latitude, lng: _origin?.longitude);
  }

  Future<void> _onDriverTap(BuildContext context, DriverCandidate driver) async {
    final provider = context.read<NearbyProvider>();
    provider.select(driver);
    final chosen = await showDriverBottomSheet(context, driver: driver);
    if (!context.mounted) return;
    if (chosen != null) {
      // Keep the pick in the provider: the request screen reads it and the
      // server ultimately matches the nearest available driver at dispatch.
      provider.select(chosen);
      context.push('/request');
    } else {
      provider.select(null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NearbyProvider>();

    if (_origin == null) {
      return _buildLocationGate(context, provider);
    }

    final selectedId = provider.selectedDriver?.driverId;

    final markers = <Marker>[
      // The caller's position, with a soft radius circle for the "pulse".
      Marker(
        point: _origin!,
        width: 36,
        height: 36,
        child: Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: AppColors.primary,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 3),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.25),
                blurRadius: 8,
              ),
            ],
          ),
          child: const Center(
            child: Icon(Icons.person_pin_circle, color: Colors.white, size: 18),
          ),
        ),
      ),
      for (final candidate in provider.candidates)
        Marker(
          point: candidate.location,
          width: 44,
          height: 64,
          alignment: Alignment.topCenter,
          child: SizedBox(
            width: 44,
            height: 64,
            child: DriverMarker(
              candidate: candidate,
              selected: candidate.driverId == selectedId,
              onTap: () => _onDriverTap(context, candidate),
            ),
          ),
        ),
    ];

    final serviceChips = <Widget>[];
    for (final (value, label) in _services) {
      final selected = provider.serviceType == value;
      serviceChips.add(ChoiceChip(
        label: Text(label),
        selected: selected,
        selectedColor: AppColors.primary,
        onSelected: (nowSelected) {
          if (nowSelected) _onServiceChanged(context, value, label);
        },
      ));
    }

    return Stack(
      children: [
        FlutterMap(
          mapController: _mapController,
          options: MapOptions(
            initialCenter: LatLng(_origin!.latitude, _origin!.longitude),
            initialZoom: 15,
            minZoom: 10,
            maxZoom: 18,
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'towing_emergency',
            ),
            CircleLayer(
              circles: [
                CircleMarker(
                  point: _origin!,
                  radius: 400,
                  useRadiusInMeter: true,
                  color: AppColors.primary.withValues(alpha: 0.12),
                  borderStrokeWidth: 2,
                  borderColor: AppColors.primary.withValues(alpha: 0.35),
                ),
              ],
            ),
            MarkerLayer(markers: markers),
          ],
        ),
        // Service-type selector shown on top of the map.
        Align(
          alignment: Alignment.topCenter,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: SafeArea(
              child: Wrap(
                spacing: 8,
                runSpacing: 4,
                alignment: WrapAlignment.start,
                children: serviceChips,
              ),
            ),
          ),
        ),
        // Recenter + request entry.
        Align(
          alignment: Alignment.bottomRight,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: SafeArea(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  FloatingActionButton(
                    onPressed: () => _mapController.move(_origin!, 15),
                    tooltip: 'Recenter on my location',
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    child: const Icon(Icons.my_location),
                  ),
                  const SizedBox(height: 12),
                  FloatingActionButton.extended(
                    onPressed: () => context.push('/request'),
                    icon: const Icon(Icons.add),
                    label: const Text('Request'),
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  /// Shown before a position fix: everything else is meaningless without one.
  Widget _buildLocationGate(BuildContext context, NearbyProvider provider) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.my_location, size: 64, color: AppColors.primary),
          const SizedBox(height: 16),
          Text(
            'Finding drivers near you…',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          if (_locationError != null) ...[
            const SizedBox(height: 8),
            Text(
              _locationError!,
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.danger, fontSize: 13),
            ),
          ],
          if (_locationError != null) ...[
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => _retryLocation(context),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text('Retry'),
            ),
          ],
        ],
      ),
    );
  }
}