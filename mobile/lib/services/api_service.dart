import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  static const String baseUrl = 'http://localhost:8000/api';
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
    return post('/auth/register', {'email': email, 'password': password}, auth: false);
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
    return get('/service-requests');
  }

  Future<dynamic> getServiceRequest(int id) async {
    return get('/service-requests/$id');
  }

  Future<dynamic> createServiceRequest({
    required String description,
    required String location,
  }) async {
    return post('/service-requests', {
      'description': description,
      'location': location,
    });
  }

  Future<dynamic> updateServiceRequest(int id, Map<String, dynamic> data) async {
    return patch('/service-requests/$id', data);
  }

  Future<void> deleteServiceRequest(int id) async {
    await delete('/service-requests/$id');
  }

  // Vehicle endpoints
  Future<List<dynamic>> getVehicles() async {
    return get('/vehicles');
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
    return get('/emergency-logs');
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
    return get('/db-ping', auth: false);
  }
}

// Singleton instance
final apiService = ApiService();