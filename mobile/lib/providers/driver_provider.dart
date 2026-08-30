import 'package:flutter/foundation.dart';
import 'package:towing_emergency/services/api_service.dart';
import 'package:towing_emergency/services/location_service.dart';

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
  List<Map<String, dynamic>> _assignments = const [];

  /// Jobs currently assigned to this driver, newest first.
  List<Map<String, dynamic>> get assignments => _assignments;

  /// Jobs still awaiting an accept/decline.
  List<Map<String, dynamic>> get pendingAssignments =>
      _assignments.where((a) => a['status'] == 'assigned').toList();

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

  /// Load the jobs this driver has been matched to.
  Future<void> loadAssignments() async {
    try {
      final rows = await apiService.getMyDispatches();
      _assignments = rows.map((r) => (r as Map).cast<String, dynamic>()).toList();
      notifyListeners();
    } catch (e) {
      // A driver with no profile yet has no assignments — not an error.
      _assignments = const [];
      notifyListeners();
    }
  }

  /// Move an accepted job along: enroute -> arrived -> completed.
  ///
  /// Completing releases the driver back into the available pool, so the
  /// profile is re-read alongside the job list.
  Future<bool> advance(int dispatchId, String status) async {
    _setLoading(true);
    try {
      await apiService.advanceDispatch(dispatchId, status);
      await loadProfile();
      await loadAssignments();
      return true;
    } catch (e) {
      _setError('Could not move the job to $status: $e');
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Buy more time before an unanswered offer lapses.
  Future<bool> extend(int dispatchId) async {
    _setLoading(true);
    try {
      await apiService.extendDispatch(dispatchId);
      await loadAssignments();
      return true;
    } catch (e) {
      _setError('Could not extend: $e');
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Accept or decline an assigned job.
  ///
  /// Accepting moves the driver to `enroute`; declining returns them to the
  /// available pool so the request can be matched to someone else. Either way
  /// the profile and the job list are re-read, since the backend changes both.
  Future<bool> respond(int dispatchId, String status) async {
    _setLoading(true);
    try {
      await apiService.respondDispatch(dispatchId, status);
      await loadProfile();
      await loadAssignments();
      return true;
    } catch (e) {
      _setError('Could not $status the job: $e');
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Read the device's real position.
  ///
  /// Previously returned a hardcoded San Francisco constant, which meant
  /// every driver published the same point and 'nearest driver' matching
  /// was meaningless. Failures now surface instead of silently publishing
  /// a position the driver has never been near.
  Future<bool> capturePhoneLocation({double? lat, double? lng}) async {
    if (lat != null && lng != null) {
      _latitude = lat;
      _longitude = lng;
      notifyListeners();
      return true;
    }
    try {
      final position = await locationService.current();
      _latitude = position.latitude;
      _longitude = position.longitude;
      _error = null;
      notifyListeners();
      return true;
    } on LocationException catch (e) {
      _setError(e.message);
      return false;
    }
  }

  /// Go active: online + available, publishing the phone location so the
  /// dispatcher can match against it.
  Future<void> goActive() async {
    // Refuse to go online without a real fix: an 'available' driver with
    // the wrong coordinates is worse than one who is offline, because
    // dispatch will confidently send a client to them.
    if (!await capturePhoneLocation()) {
      return;
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
    // Re-read the device first. This used to republish the cached
    // coordinates, which was invisible while the position was a hardcoded
    // constant that never changed — but means a driver who has moved
    // across town would keep advertising where they used to be.
    if (!await capturePhoneLocation()) return;
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
