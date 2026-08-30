import 'package:geolocator/geolocator.dart';

/// Why a location read failed, so callers can say something useful.
///
/// These are distinguished on purpose. "Turn on location services" and "you
/// denied permission, open Settings to change it" need different words and
/// different buttons, and both are different from a timeout on a bad signal.
enum LocationFailure {
  servicesDisabled,
  permissionDenied,
  permissionDeniedForever,
  timeout,
  unavailable,
}

class LocationException implements Exception {
  const LocationException(this.failure, this.message);

  final LocationFailure failure;
  final String message;

  /// Whether the user can fix this from inside the app.
  bool get isRecoverable =>
      failure != LocationFailure.permissionDeniedForever &&
      failure != LocationFailure.servicesDisabled;

  @override
  String toString() => message;
}

/// Reads the device's real position.
///
/// Replaces the hardcoded `37.7749, -122.4194` that both the request screen and
/// the driver console used to publish. That constant made every mobile user —
/// driver and commuter alike — report the same point in San Francisco, so
/// distance was always ~0 km, ETA ~0 min, and "nearest driver" matching was
/// meaningless. The backend could not tell: it just measured the distance
/// between two identical fabrications.
///
/// Failures throw [LocationException] rather than falling back to a default.
/// Quietly substituting a position is worse than an honest error here: a driver
/// who declined the permission would be entered into the dispatch pool at
/// coordinates they have never been near.
class LocationService {
  const LocationService();

  static const _timeout = Duration(seconds: 15);

  /// Current position, requesting permission if needed.
  Future<Position> current() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw const LocationException(
        LocationFailure.servicesDisabled,
        'Location services are turned off. Enable them to continue.',
      );
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.deniedForever) {
      throw const LocationException(
        LocationFailure.permissionDeniedForever,
        'Location permission is permanently denied. Enable it in Settings.',
      );
    }
    if (permission == LocationPermission.denied) {
      throw const LocationException(
        LocationFailure.permissionDenied,
        'Location permission is required to dispatch a driver to you.',
      );
    }

    try {
      return await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: _timeout,
        ),
      );
    } on Exception catch (e) {
      // A timeout usually means a weak fix rather than a broken device, so try
      // the last known position before giving up entirely.
      final last = await Geolocator.getLastKnownPosition();
      if (last != null) return last;
      throw LocationException(
        LocationFailure.timeout,
        'Could not get a location fix: $e',
      );
    }
  }

  /// A stream of positions for live tracking, throttled by distance so a
  /// stationary driver is not sending redundant updates or draining battery.
  Stream<Position> watch({int distanceFilterMetres = 25}) {
    return Geolocator.getPositionStream(
      locationSettings: LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: distanceFilterMetres,
      ),
    );
  }
}

const locationService = LocationService();
