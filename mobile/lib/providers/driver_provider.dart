import 'package:flutter/foundation.dart';
import 'package:towing_emergency/services/api_service.dart';

/// Holds the driver's live availability/position state for the console UI.
///
/// Matches the semantics used by the backend + web console:
///   - "Active"  = online AND available, with a (phone) position set. This is
///     the only state where the driver's location is used for dispatch.
///   - "Offline" = not online, OR busy handling a request (enroute/assigned).
///     In this state the driver is NOT matchable and is shown as offline.
class DriverProvider extends ChangeNotifier {
  bool _isLoading = false;
  String? _error;
  bool _isOnline = false;
  String _currentStatus = 'off_duty';
  double? _latitude;
  double? _longitude;

  bool get isLoading => _isLoading;
  String? get error => _error;

  bool get isOnline => _isOnline;

  /// The driver counts as "active" only when online + available + has a fix.
  bool get isActive =>
      _isOnline && _currentStatus == 'available' && _latitude != null;

  /// Busy handling a request (assigned/enroute) — treated as offline.
  bool get isBusy =>
      _isOnline && (_currentStatus == 'enroute' || _currentStatus == 'assigned');

  String get currentStatus => _currentStatus;
  double? get latitude => _latitude;
  double? get longitude => _longitude;

  /// Whether a (simulated) phone position has been captured.
  bool get hasPosition => _latitude != null && _longitude != null;

  /// Load the driver's persisted profile (absent profile -> offline by default).
  Future<void> loadProfile() async {
    _setLoading(true);
    try {
      final data = await apiService.getMyDriverProfile();
      _isOnline = data['is_online'] == true;
      _currentStatus = data['current_status'] as String? ?? 'off_duty';
      _latitude = data['current_lat'] as double?;
      _longitude = data['current_lng'] as double?;
      notifyListeners();
    } catch (e) {
      // 404 (no profile yet) is expected — treat as offline.
      _isOnline = false;
      _currentStatus = 'off_duty';
      _latitude = null;
      _longitude = null;
      notifyListeners();
    } finally {
      _setLoading(false);
    }
  }

  /// Capture the phone's location (simulated here, following the request
  /// screen's convention; swap in a real geolocator in production).
  void capturePhoneLocation({double? lat, double? lng}) {
    const defaultLat = 37.7749;
    const defaultLng = -122.4194;
    _latitude = lat ?? defaultLat;
    _longitude = lng ?? defaultLng;
    notifyListeners();
  }

  /// Go active: online + available, publishing the phone location so the
  /// dispatcher can match against it.
  Future<void> goActive() async {
    if (!hasPosition) {
      capturePhoneLocation();
    }
    _setLoading(true);
    try {
      final data = await apiService.updateDriverAvailability(
        isOnline: true,
        currentStatus: 'available',
        currentLat: _latitude,
        currentLng: _longitude,
      );
      _apply(data);
      notifyListeners();
    } catch (e) {
      _setError('Could not go online: $e');
    } finally {
      _setLoading(false);
    }
  }

  /// Refresh the position heartbeat while staying active.
  Future<void> refreshPosition() async {
    if (!_isOnline) return;
    _setLoading(true);
    try {
      final data = await apiService.updateDriverAvailability(
        isOnline: _isOnline,
        currentStatus: _currentStatus,
        currentLat: _latitude,
        currentLng: _longitude,
      );
      _apply(data);
      notifyListeners();
    } catch (e) {
      _setError('Could not update position: $e');
    } finally {
      _setLoading(false);
    }
  }

  /// Go offline: not matchable, stop publishing a location.
  Future<void> goOffline() async {
    _setLoading(true);
    try {
      final data = await apiService.updateDriverAvailability(
        isOnline: false,
        currentStatus: 'off_duty',
      );
      _apply(data);
      notifyListeners();
    } catch (e) {
      _setError('Could not go offline: $e');
    } finally {
      _setLoading(false);
    }
  }

  void _apply(Map<String, dynamic> data) {
    _isOnline = data['is_online'] == true;
    _currentStatus = data['current_status'] as String? ?? _currentStatus;
    final lat = data['current_lat'];
    final lng = data['current_lng'];
    if (lat is double && lng is double) {
      _latitude = lat;
      _longitude = lng;
    }
  }

  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  void _setError(String e) {
    _error = e;
    notifyListeners();
  }
}
