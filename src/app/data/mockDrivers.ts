import { Driver } from '../utils/routing';

export const mockDrivers: Driver[] = [
  {
    id: 'DRV-001',
    name: 'Mike Johnson',
    vehicle: 'Tow Truck #42',
    location: { lat: 40.7500, lng: -74.0300 },
    status: 'available',
  },
  {
    id: 'DRV-002',
    name: 'David Brown',
    vehicle: 'Tow Truck #38',
    location: { lat: 40.7250, lng: -74.0150 },
    status: 'busy',
    activeRequestId: 'REQ-8470',
  },
  {
    id: 'DRV-003',
    name: 'Sarah Thompson',
    vehicle: 'Tow Truck #55',
    location: { lat: 40.7400, lng: -74.0200 },
    status: 'busy',
    activeRequestId: 'REQ-8469',
  },
  {
    id: 'DRV-004',
    name: 'Tom Wilson',
    vehicle: 'Tow Truck #29',
    location: { lat: 40.7050, lng: -74.0050 },
    status: 'available',
  },
  {
    id: 'DRV-005',
    name: 'Lisa Anderson',
    vehicle: 'Tow Truck #67',
    location: { lat: 40.7350, lng: -74.0280 },
    status: 'available',
  },
  {
    id: 'DRV-006',
    name: 'James Martinez',
    vehicle: 'Tow Truck #51',
    location: { lat: 40.7180, lng: -74.0090 },
    status: 'available',
  },
  {
    id: 'DRV-007',
    name: 'Rachel Kim',
    vehicle: 'Tow Truck #73',
    location: { lat: 40.7450, lng: -74.0350 },
    status: 'offline',
  },
  {
    id: 'DRV-008',
    name: 'Chris Davis',
    vehicle: 'Tow Truck #44',
    location: { lat: 40.7100, lng: -74.0120 },
    status: 'available',
  },
];
