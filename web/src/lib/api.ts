import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_URL}/api`,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        if (this.accessToken && config.headers) {
          config.headers.Authorization = `Bearer ${this.accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config;
        if (error.response?.status === 401 && originalRequest && !originalRequest.headers?.['X-Retry']) {
          originalRequest.headers = originalRequest.headers || {};
          originalRequest.headers['X-Retry'] = 'true';
          try {
            await this.refreshToken();
            return this.client(originalRequest);
          } catch {
            this.clearToken();
            if (typeof window !== 'undefined') {
              window.location.href = '/login';
            }
          }
        }
        return Promise.reject(error);
      }
    );

    // Load token from localStorage on init
    if (typeof window !== 'undefined') {
      this.accessToken = localStorage.getItem('access_token');
    }
  }

  setToken(token: string) {
    this.accessToken = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', token);
    }
  }

  clearToken() {
    this.accessToken = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
    }
  }

  async refreshToken() {
    // In a real app, you'd call a refresh endpoint
    // For now, we'll just clear the token and redirect to login
    throw new Error('Token refresh not implemented');
  }

  // Auth endpoints
  async register(email: string, password: string) {
    const response = await this.client.post('/auth/register', { email, password });
    return response.data;
  }

  async login(email: string, password: string) {
    const response = await this.client.post('/auth/jwt/login', 
      new URLSearchParams({ username: email, password }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    );
    if (response.data.access_token) {
      this.setToken(response.data.access_token);
    }
    return response.data;
  }

  async logout() {
    this.clearToken();
  }

  // Service Request endpoints
  async getServiceRequests() {
    const response = await this.client.get('/service-requests');
    return response.data;
  }

  async getServiceRequest(id: number) {
    const response = await this.client.get(`/service-requests/${id}`);
    return response.data;
  }

  async createServiceRequest(data: {
    description: string;
    location: string;
    service_type?: string;
    vehicle_type?: string;
    name?: string;
    phone_number?: string;
    latitude?: number | null;
    longitude?: number | null;
  }) {
    const response = await this.client.post('/service-requests', data);
    return response.data;
  }

  async updateServiceRequest(id: number, data: Partial<{ description: string; location: string; status: string; service_type: string; vehicle_type: string; name: string; phone_number: string; latitude: number; longitude: number }>) {
    const response = await this.client.patch(`/service-requests/${id}`, data);
    return response.data;
  }

  async deleteServiceRequest(id: number) {
    const response = await this.client.delete(`/service-requests/${id}`);
    return response.data;
  }

  // ---- Routing / dispatch ----

  // Driver availability + live position (upsert).
  async updateDriverAvailability(data: {
    is_online?: boolean;
    current_status?: string;
    current_lat?: number;
    current_lng?: number;
  }) {
    const response = await this.client.put('/drivers/me', data);
    return response.data;
  }

  async getMyDriverProfile() {
    const response = await this.client.get('/drivers/me');
    return response.data;
  }

  // Nearest available drivers for a coordinate (preview, no assignment).
  async getAvailableDrivers(lat: number, lng: number) {
    const response = await this.client.get(`/dispatch/available?lat=${lat}&lng=${lng}`);
    return response.data;
  }

  // Match the nearest driver to a pending request (creates the assignment).
  async createDispatch(requestId: number) {
    const response = await this.client.post('/dispatch', { request_id: requestId });
    return response.data;
  }

  // The requester's view of a live assignment.
  async getRequestDispatch(requestId: number) {
    const response = await this.client.get(`/dispatch/request/${requestId}`);
    return response.data;
  }

  // The assigned driver accepts or declines.
  async respondDispatch(dispatchId: number, status: 'accepted' | 'declined') {
    const response = await this.client.post(`/dispatch/${dispatchId}/respond`, { status });
    return response.data;
  }

  // Vehicle endpoints
  async getVehicles() {
    const response = await this.client.get('/vehicles');
    return response.data;
  }

  async getVehicle(id: number) {
    const response = await this.client.get(`/vehicles/${id}`);
    return response.data;
  }

  async createVehicle(data: { make: string; model: string; year: number; plate_number: string }) {
    const response = await this.client.post('/vehicles', data);
    return response.data;
  }

  async updateVehicle(id: number, data: Partial<{ make: string; model: string; year: number; plate_number: string }>) {
    const response = await this.client.patch(`/vehicles/${id}`, data);
    return response.data;
  }

  async deleteVehicle(id: number) {
    const response = await this.client.delete(`/vehicles/${id}`);
    return response.data;
  }

  // Emergency Log endpoints
  async getEmergencyLogs() {
    const response = await this.client.get('/emergency-logs');
    return response.data;
  }

  async createEmergencyLog(data: { incident_type: string; description: string }) {
    const response = await this.client.post('/emergency-logs', data);
    return response.data;
  }

  // Health check
  async healthCheck() {
    const response = await this.client.get('/db-ping');
    return response.data;
  }
}

export const apiClient = new ApiClient();
export default apiClient;