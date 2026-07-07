import 'package:flutter/foundation.dart';
import 'package:towing_emergency/services/api_service.dart';

class RequestProvider with ChangeNotifier {
  bool _isLoading = false;
  String? _error;
  List<dynamic> _requests = [];

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
  }) async {
    _setLoading(true);
    _clearError();
    
    try {
      final request = await apiService.createServiceRequest(
        description: description,
        location: location,
      );
      _requests.insert(0, request);
      notifyListeners();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    } finally {
      _setLoading(false);
    }
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