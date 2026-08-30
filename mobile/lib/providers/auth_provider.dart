import 'package:flutter/foundation.dart';
import 'package:towing_emergency/services/api_service.dart';
import 'package:towing_emergency/services/push_service.dart';

class AuthProvider with ChangeNotifier {
  bool _isLoading = false;
  String? _error;
  bool _isLoggedIn = false;
  String _role = 'commuter';

  /// The signed-in user's role. Drives which surfaces are offered.
  String get role => _role;

  /// Whether this account is approved to drive.
  ///
  /// The Driver Console used to be shown to everyone, and going online
  /// silently promoted the caller to a driver — so a commuter could make
  /// themselves dispatchable. The server refuses that now; this just stops
  /// offering a button that would only produce a 403.
  bool get canDrive =>
      _role == 'driver' || _role == 'company' || _role == 'admin';

  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isLoggedIn => _isLoggedIn;

  // Check if user is logged in on app start
  Future<void> checkAuthStatus() async {
    final token = await apiService.getToken();
    _isLoggedIn = token != null;
    if (_isLoggedIn) {
      await _loadRole();
    }
    notifyListeners();
  }

  /// Read the role from the server. A stale or rejected token leaves the
  /// user as a commuter, which shows the safe subset of the app.
  Future<void> _loadRole() async {
    try {
      final me = await apiService.getMe();
      _role = (me['role'] as String?) ?? 'commuter';
    } catch (_) {
      _role = 'commuter';
    }
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
      await _loadRole();
      // The token is only useful once the server knows whose it is.
      await pushService.registerForUser();
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
    // Before clearing the token, or the next user of this phone inherits
    // the previous one's job notifications.
    await pushService.unregister();
    await apiService.logout();
    _isLoggedIn = false;
    _role = 'commuter';
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