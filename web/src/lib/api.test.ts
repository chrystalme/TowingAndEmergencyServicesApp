// Mock axios before importing apiClient
jest.mock('axios');
import axios from 'axios';
import { apiClient } from '@/lib/api';

const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('ApiClient - basic', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('token management', () => {
    it('stores token in localStorage', () => {
      apiClient.setToken('test-token');
      expect(localStorage.setItem).toHaveBeenCalledWith('access_token', 'test-token');
    });

    it('clears token from localStorage', () => {
      apiClient.clearToken();
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    });
  });

  describe('logout', () => {
    it('clears token', () => {
      apiClient.setToken('some-token');
      apiClient.logout();
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    });
  });
});