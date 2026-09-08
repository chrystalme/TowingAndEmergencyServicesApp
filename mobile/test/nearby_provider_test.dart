import 'package:flutter_test/flutter_test.dart';
import 'package:towing_emergency/models/driver_candidate.dart';
import 'package:towing_emergency/providers/nearby_provider.dart';
import 'package:towing_emergency/services/api_service.dart';

/// A fake [ApiService] that returns canned candidates without touching the
/// network, so [NearbyProvider] is testable in isolation.
class _FakeApiService extends ApiService {
  _FakeApiService(List<Map<String, dynamic>> rows, {this.throwOnCall = false})
      : _rows = rows;

  final List<Map<String, dynamic>> _rows;
  final bool throwOnCall;

  int calls = 0;
  double? lastLat;
  double? lastLng;
  String? lastServiceType;
  String? lastVehicleType;

  @override
  Future<List<dynamic>> getAvailableDrivers(
    double lat,
    double lng, {
    String serviceType = 'towing',
    String vehicleType = 'car',
  }) async {
    calls++;
    lastLat = lat;
    lastLng = lng;
    lastServiceType = serviceType;
    lastVehicleType = vehicleType;
    if (throwOnCall) throw StateError('network down');
    return _rows.cast<dynamic>().toList();
  }
}

Map<String, dynamic> _candidate(int id, {String? name, double? price}) => {
      'driver_id': id,
      'name': name,
      'email': 'driver$id@example.com',
      'current_lat': 37.77,
      'current_lng': -122.42,
      'distance_km': 2.5,
      'eta_minutes': 4.0,
      'price_estimate': price,
      'vehicle_make': 'Mercedes',
      'vehicle_model': 'Sprinter',
      'vehicle_plate': 'TRUCK-1-NG',
    };

void main() {
  test('refresh populates candidates and clears loading', () async {
    final api = _FakeApiService([_candidate(1), _candidate(2, price: 18500)]);
    final provider = NearbyProvider(apiService: api);

    await provider.refresh(lat: 37.77, lng: -122.42);

    expect(provider.isLoading, isFalse);
    expect(provider.error, isNull);
    expect(provider.candidates.length, 2);
    expect(provider.candidates.first.driverId, 1);
    expect(provider.candidates.first.priceEstimate, isNull);
    expect(provider.candidates.last.priceEstimate, 18500);
    expect(api.calls, 1);
    expect(api.lastServiceType, 'towing');
    expect(api.lastVehicleType, 'car');
  });

  test('serviceType/vehicleType are forwarded to the API', () async {
    final api = _FakeApiService([_candidate(1)]);
    final provider = NearbyProvider(apiService: api);
    provider.serviceType = 'recovery';
    provider.vehicleType = 'suv';

    await provider.refresh(lat: 1.0, lng: 2.0);

    expect(api.lastServiceType, 'recovery');
    expect(api.lastVehicleType, 'suv');
  });

  test('a failing call sets error and does not throw', () async {
    final api = _FakeApiService([], throwOnCall: true);
    final provider = NearbyProvider(apiService: api);

    bool notified = false;
    provider.addListener(() => notified = true);
    await provider.refresh(lat: 0.0, lng: 0.0);

    expect(provider.error, isNotNull);
    expect(provider.candidates, isEmpty);
    expect(notified, isTrue);
  });

  test('select stores the chosen driver for the request screen', () {
    final provider = NearbyProvider(apiService: _FakeApiService([]));
    final driver = DriverCandidate.fromJson(_candidate(7, price: 20000));

    provider.select(driver);
    expect(provider.selectedDriver?.driverId, 7);

    provider.select(null);
    expect(provider.selectedDriver, isNull);
  });
}