import 'package:flutter/foundation.dart';
import 'package:towing_emergency/services/api_service.dart';

class RequestProvider with ChangeNotifier {
  bool _isLoading = false;
  String? _error;
  List<dynamic> _requests = [];
  Map<String, dynamic>? _lastDispatch;

  /// The assignment produced by the most recent [dispatchRequest].
  Map<String, dynamic>? get lastDispatch => _lastDispatch;

  bool get isLoading => _isLoading;
  String? get error => _error;
  List<dynamic> get requests => _requests;

  // Fetch all requests
  Future<void> fetchRequests() async {
    _setLoading(true);
    _clearError();
    
    try {
      _requests = await apiService.getServiceRequests();
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }

  // Create request
  Future<bool> createRequest({
    required String description,
    required String location,
    String serviceType = 'towing',
    String vehicleType = 'car',
    String name = '',
    String phoneNumber = '',
    double? latitude,
    double? longitude,
  }) async {
    _setLoading(true);
    _clearError();
    
    try {
      final request = await apiService.createServiceRequest(
        description: description,
        location: location,
        serviceType: serviceType,
        vehicleType: vehicleType,
        name: name,
        phoneNumber: phoneNumber,
        latitude: latitude,
        longitude: longitude,
      );
      _requests.insert(0, request);
      notifyListeners();
      // Filing a request is only half the flow — nothing happens until a
      // driver is matched. The web app dispatches straight after creating,
      // so mobile requests used to sit pending forever.
      await dispatchRequest(request['id'] as int);
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Match the nearest available driver to a freshly filed request.
  ///
  /// A failure here is not a failed request: the request exists and can be
  /// dispatched later, so this records the reason rather than throwing.
  Future<void> dispatchRequest(int requestId) async {
    _lastDispatch = null;
    try {
      final match = await apiService.createDispatch(requestId);
      _lastDispatch = (match['dispatch'] as Map).cast<String, dynamic>();
      await fetchRequests();
    } catch (e) {
      _setError('No driver available yet: $e');
    }
    notifyListeners();
  }

  // Refresh requests
  Future<void> refresh() async {
    await fetchRequests();
  }

  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  void _setError(String error) {
    _error = error;
    notifyListeners();
  }

  void _clearError() {
    _error = null;
    notifyListeners();
  }
}