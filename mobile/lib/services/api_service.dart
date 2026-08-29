import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  // Configurable at build/run time so one codebase serves every target:
  //   iOS simulator / desktop : the default below (shares the host network)
  //   Android emulator        : --dart-define=API_BASE_URL=http://10.0.2.2:8000/api
  //   physical device         : --dart-define=API_BASE_URL=http://<lan-ip>:8000/api
  //   deployed                : --dart-define=API_BASE_URL=https://api.example.com/api
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000/api',
  );
  static const String _tokenKey = 'access_token';
  
  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  String? _accessToken;

  // Get stored token
  Future<String?> getToken() async {
    if (_accessToken != null) return _accessToken;
    _accessToken = await _storage.read(key: _tokenKey);
    return _accessToken;
  }

  // Store token
  Future<void> setToken(String token) async {
    _accessToken = token;
    await _storage.write(key: _tokenKey, value: token);
  }

  // Clear token
  Future<void> clearToken() async {
    _accessToken = null;
    await _storage.delete(key: _tokenKey);
  }

  // Create headers with auth
  Future<Map<String, String>> _headers({bool auth = true}) async {
    final headers = {
      'Content-Type': 'application/json',
    };
    
    if (auth) {
      final token = await getToken();
      if (token != null) {
        headers['Authorization'] = 'Bearer $token';
      }
    }
    return headers;
  }

  // Handle response
  dynamic _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return json.decode(response.body);
    }
    
    String errorMessage;
    try {
      final error = json.decode(response.body);
      errorMessage = error['detail'] ?? error['message'] ?? 'Request failed';
    } catch (_) {
      errorMessage = 'Request failed with status: ${response.statusCode}';
    }
    
    // If 401, clear token
    if (response.statusCode == 401) {
      clearToken();
    }
    
    throw Exception(errorMessage);
  }

  // GET request
  Future<dynamic> get(String endpoint, {bool auth = true}) async {
    final headers = await _headers(auth: auth);
    final response = await http.get(
      Uri.parse('$baseUrl$endpoint'),
      headers: headers,
    );
    return _handleResponse(response);
  }

  // POST request
  Future<dynamic> post(String endpoint, Map<String, dynamic> body, {bool auth = true}) async {
    final headers = await _headers(auth: auth);
    final response = await http.post(
      Uri.parse('$baseUrl$endpoint'),
      headers: headers,
      body: json.encode(body),
    );
    return _handleResponse(response);
  }

  // PATCH request
  Future<dynamic> patch(String endpoint, Map<String, dynamic> body, {bool auth = true}) async {
    final headers = await _headers(auth: auth);
    final response = await http.patch(
      Uri.parse('$baseUrl$endpoint'),
      headers: headers,
      body: json.encode(body),
    );
    return _handleResponse(response);
  }

  // PUT request
  Future<dynamic> put(String endpoint, Map<String, dynamic> body, {bool auth = true}) async {
    final headers = await _headers(auth: auth);
    final response = await http.put(
      Uri.parse('$baseUrl$endpoint'),
      headers: headers,
      body: json.encode(body),
    );
    return _handleResponse(response);
  }

  // DELETE request
  Future<dynamic> delete(String endpoint, {bool auth = true}) async {
    final headers = await _headers(auth: auth);
    final response = await http.delete(
      Uri.parse('$baseUrl$endpoint'),
      headers: headers,
    );
    return _handleResponse(response);
  }

  // Auth endpoints
  Future<Map<String, dynamic>> register(String email, String password) async {
    return (await post('/auth/register', {'email': email, 'password': password}, auth: false))
        as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final headers = {'Content-Type': 'application/x-www-form-urlencoded'};
    final response = await http.post(
      Uri.parse('$baseUrl/auth/jwt/login'),
      headers: headers,
      body: 'username=${Uri.encodeComponent(email)}&password=${Uri.encodeComponent(password)}',
    );
    
    final data = _handleResponse(response);
    if (data['access_token'] != null) {
      await setToken(data['access_token']);
    }
    return data;
  }

  Future<void> logout() async {
    await clearToken();
  }

  // Service Request endpoints
  Future<List<dynamic>> getServiceRequests() async {
    return (await get('/service-requests')) as List<dynamic>;
  }

  Future<dynamic> getServiceRequest(int id) async {
    return get('/service-requests/$id');
  }

  Future<dynamic> createServiceRequest({
    required String description,
    required String location,
    String serviceType = 'towing',
    String vehicleType = 'car',
    String name = '',
    String phoneNumber = '',
    double? latitude,
    double? longitude,
  }) async {
    return post('/service-requests', {
      'description': description,
      'location': location,
      'service_type': serviceType,
      'vehicle_type': vehicleType,
      'name': name,
      'phone_number': phoneNumber,
      'latitude': latitude,
      'longitude': longitude,
    });
  }

  // ---- Routing / dispatch ----

  // Driver availability + live position (upsert).
  Future<dynamic> updateDriverAvailability({
    required bool isOnline,
    String currentStatus = 'available',
    double? currentLat,
    double? currentLng,
  }) async {
    return put('/drivers/me', {
      'is_online': isOnline,
      'current_status': currentStatus,
      'current_lat': currentLat,
      'current_lng': currentLng,
    });
  }

  Future<dynamic> getMyDriverProfile() async {
    return get('/drivers/me');
  }

  // Nearest available drivers for a coordinate (preview, no assignment).
  Future<List<dynamic>> getAvailableDrivers(double lat, double lng) async {
    return (await get('/dispatch/available?lat=$lat&lng=$lng')) as List<dynamic>;
  }

  // Match the nearest driver to a pending request.
  Future<dynamic> createDispatch(int requestId) async {
    return post('/dispatch', {'request_id': requestId});
  }

  // The requester's view of a live assignment.
  Future<dynamic> getRequestDispatch(int requestId) async {
    return get('/dispatch/request/$requestId');
  }

  // The assigned driver accepts or declines.
  Future<dynamic> respondDispatch(int dispatchId, String status) async {
    return post('/dispatch/$dispatchId/respond', {'status': status});
  }

  Future<dynamic> updateServiceRequest(int id, Map<String, dynamic> data) async {
    return patch('/service-requests/$id', data);
  }

  Future<void> deleteServiceRequest(int id) async {
    await delete('/service-requests/$id');
  }

  // Vehicle endpoints
  Future<List<dynamic>> getVehicles() async {
    return (await get('/vehicles')) as List<dynamic>;
  }

  Future<dynamic> createVehicle({
    required String make,
    required String model,
    required int year,
    required String plateNumber,
  }) async {
    return post('/vehicles', {
      'make': make,
      'model': model,
      'year': year,
      'plate_number': plateNumber,
    });
  }

  // Emergency Log endpoints
  Future<List<dynamic>> getEmergencyLogs() async {
    return (await get('/emergency-logs')) as List<dynamic>;
  }

  Future<dynamic> createEmergencyLog({
    required String incidentType,
    required String description,
  }) async {
    return post('/emergency-logs', {
      'incident_type': incidentType,
      'description': description,
    });
  }

  // Health check
  Future<Map<String, dynamic>> healthCheck() async {
    return (await get('/db-ping', auth: false)) as Map<String, dynamic>;
  }
}

// Singleton instance
final apiService = ApiService();