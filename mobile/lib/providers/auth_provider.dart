import 'package:flutter/foundation.dart';
import 'package:towing_emergency/services/api_service.dart';

class AuthProvider with ChangeNotifier {
  bool _isLoading = false;
  String? _error;
  bool _isLoggedIn = false;

  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isLoggedIn => _isLoggedIn;

  // Check if user is logged in on app start
  Future<void> checkAuthStatus() async {
    final token = await apiService.getToken();
    _isLoggedIn = token != null;
    notifyListeners();
  }

  // Register
  Future<bool> register(String email, String password) async {
    _setLoading(true);
    _clearError();
    
    try {
      await apiService.register(email, password);
      _isLoggedIn = false; // User needs to login after register
      notifyListeners();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    } finally {
      _setLoading(false);
    }
  }

  // Login
  Future<bool> login(String email, String password) async {
    _setLoading(true);
    _clearError();
    
    try {
      await apiService.login(email, password);
      _isLoggedIn = true;
      notifyListeners();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    } finally {
      _setLoading(false);
    }
  }

  // Logout
  Future<void> logout() async {
    await apiService.logout();
    _isLoggedIn = false;
    notifyListeners();
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