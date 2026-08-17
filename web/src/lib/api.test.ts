// Mock axios before importing apiClient
//
// The auto-mock (`jest.mock('axios')`) replaces axios.create with a fn that
// returns undefined, which crashes ApiClient's constructor at
// `this.client.interceptors.request.use(...)`. So we provide a manual factory
// that returns a usable stub client with interceptor wiring.
jest.mock('axios', () => {
  const mockClient = {
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  };
  return {
    create: jest.fn(() => mockClient),
  };
});

import axios from 'axios';
import { apiClient } from '@/lib/api';

const mockedAxios = axios as jest.Mocked<typeof axios>;

// In jsdom, `localStorage` methods live on the shared Storage.prototype and the
// instance is a getter, so jest.spyOn(localStorage, 'setItem') silently no-ops.
// Spy on the prototype instead — the canonical working pattern.
const storageProto = Object.getPrototypeOf(localStorage) as Storage;

describe('ApiClient - basic', () => {
  beforeEach(() => {
    localStorage.clear();
    jest.restoreAllMocks();
  });

  describe('token management', () => {
    it('stores token in localStorage', () => {
      const spy = jest.spyOn(storageProto, 'setItem');
      apiClient.setToken('test-token');
      expect(spy).toHaveBeenCalledWith('access_token', 'test-token');
    });

    it('clears token from localStorage', () => {
      const spy = jest.spyOn(storageProto, 'removeItem');
      apiClient.clearToken();
      expect(spy).toHaveBeenCalledWith('access_token');
    });
  });

  describe('logout', () => {
    it('clears token', () => {
      const spy = jest.spyOn(storageProto, 'removeItem');
      apiClient.setToken('some-token');
      apiClient.logout();
      expect(spy).toHaveBeenCalledWith('access_token');
    });
  });

  describe('client construction', () => {
    it('creates an axios client pointed at the /api base', () => {
      expect(mockedAxios.create).toHaveBeenCalled();
      const createCall = mockedAxios.create.mock.calls[0];
      expect(createCall?.[0]?.baseURL).toMatch(/\/api$/);
    });
  });
});
