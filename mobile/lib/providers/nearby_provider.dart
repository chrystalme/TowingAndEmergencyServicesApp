import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:latlong2/latlong.dart';

import '../models/driver_candidate.dart';
import '../services/api_service.dart' as api;

/// The "drivers near me" data behind the map screen.
///
/// Holds the search origin, the parsed list of [DriverCandidate]s and the
/// service/vehicle filters the backend uses to quote prices. The map screen
/// calls [setVisible] when it appears so a slow periodic refresh keeps the
/// list warm; the moment it disappears the timer is stopped, so no work
/// happens while the user is on another tab.
class NearbyProvider with ChangeNotifier {
  NearbyProvider({
    api.ApiService? apiService,
    this.refreshInterval = const Duration(seconds: 30),
  }) : _api = apiService ?? api.apiService;

  final api.ApiService _api;
  final Duration refreshInterval;

  LatLng? _origin;
  List<DriverCandidate> _candidates = [];
  bool _isLoading = false;
  String? _error;
  String _serviceType = 'towing';
  String _vehicleType = 'car';
  DriverCandidate? _selectedDriver;

  Timer? _timer;
  bool _isVisible = false;
  bool _refreshing = false;

  /// Where the search is centred. Null until the first successful fix.
  LatLng? get origin => _origin;

  /// Drivers currently available, ranked by the server by distance.
  List<DriverCandidate> get candidates => _candidates;

  bool get isLoading => _isLoading;
  String? get error => _error;

  /// The service being quoted (towing / roadside / recovery).
  String get serviceType => _serviceType;
  set serviceType(String value) {
    if (_serviceType == value) return;
    _serviceType = value;
    notifyListeners();
  }

  /// The vehicle size quoted (car / van / truck…).
  String get vehicleType => _vehicleType;
  set vehicleType(String value) {
    if (_vehicleType == value) return;
    _vehicleType = value;
    notifyListeners();
  }

  /// The driver the user picked in the bottom sheet, if any.
  ///
  /// The request screen reads this to pre-fill its dispatch payload;
  /// it stays null until the map screen calls [select].
  DriverCandidate? get selectedDriver => _selectedDriver;

  void select(DriverCandidate? driver) {
    _selectedDriver = driver;
    notifyListeners();
  }

  /// Refresh the driver list, optionally at a new origin.
  ///
  /// The [lat]/[lng] default to the last known origin, so the periodic
  /// timer can just call `refresh()` and it re-queries where we are.
  Future<void> refresh({double? lat, double? lng}) async {
    if (_refreshing) return;
    final targetLat = lat ?? _origin?.latitude;
    final targetLng = lng ?? _origin?.longitude;
    if (targetLat == null || targetLng == null) return;

    _refreshing = true;
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      if (lat != null && lng != null) _origin = LatLng(lat, lng);
      final raw = await _api.getAvailableDrivers(
        targetLat,
        targetLng,
        serviceType: _serviceType,
        vehicleType: _vehicleType,
      );
      _candidates = raw
          .map((e) => DriverCandidate.fromJson(
              Map<String, dynamic>.from(e as Map)))
          .toList();
    } catch (e) {
      _error = e.toString();
    } finally {
      _refreshing = false;
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Start/stop the periodic refresh, e.g. from the map screen lifecycle.
  void setVisible(bool visible) {
    if (_isVisible == visible) return;
    _isVisible = visible;
    if (visible) {
      _timer ??= Timer.periodic(refreshInterval, (_) => refresh());
    } else {
      _timer?.cancel();
      _timer = null;
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _timer = null;
    super.dispose();
  }
}