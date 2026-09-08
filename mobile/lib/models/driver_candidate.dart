import 'package:latlong2/latlong.dart';

/// A driver that is currently available near the requester.
///
/// This is the parsed shape of one entry of `GET /dispatch/available`,
/// which the backend already ranks by distance and enriches with an
/// upfront price estimate. The map screen renders these as markers and the
/// bottom sheet shows the selected one's details.
final class DriverCandidate {
  const DriverCandidate({
    this.driverId = 0,
    this.name,
    this.email = '',
    this.currentLat = 0,
    this.currentLng = 0,
    this.distanceKm = 0,
    this.etaMinutes,
    this.priceEstimate,
    this.vehicleMake,
    this.vehicleModel,
    this.vehiclePlate,
  });

  /// The dispatch pool id, used as the stable key for this driver.
  final int driverId;
  final String? name;
  final String email;
  final double currentLat;
  final double currentLng;
  final double distanceKm;

  /// Estimated travel time to the requester, in minutes.
  final double? etaMinutes;

  /// Upfront fare quoted by the server (NGN).
  final double? priceEstimate;
  final String? vehicleMake;
  final String? vehicleModel;
  final String? vehiclePlate;

  factory DriverCandidate.fromJson(Map<String, dynamic> json) => DriverCandidate(
        driverId: (json['driver_id'] as num?)?.toInt() ?? 0,
        name: json['name'] as String?,
        email: (json['email'] as String?) ?? '',
        currentLat: (json['current_lat'] as num?)?.toDouble() ?? 0,
        currentLng: (json['current_lng'] as num?)?.toDouble() ?? 0,
        distanceKm: (json['distance_km'] as num?)?.toDouble() ?? 0,
        etaMinutes: (json['eta_minutes'] as num?)?.toDouble(),
        priceEstimate: (json['price_estimate'] as num?)?.toDouble(),
        vehicleMake: json['vehicle_make'] as String?,
        vehicleModel: json['vehicle_model'] as String?,
        vehiclePlate: json['vehicle_plate'] as String?,
      );

  /// Where this driver is on the map right now.
  LatLng get location => LatLng(currentLat, currentLng);

  /// Back to the wire shape, used by tests and any serialization needs.
  Map<String, dynamic> toJson() => {
        'driver_id': driverId,
        'name': name,
        'email': email,
        'current_lat': currentLat,
        'current_lng': currentLng,
        'distance_km': distanceKm,
        'eta_minutes': etaMinutes,
        'price_estimate': priceEstimate,
        'vehicle_make': vehicleMake,
        'vehicle_model': vehicleModel,
        'vehicle_plate': vehiclePlate,
      };
}