import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { MapPin, Clock, AlertCircle, Phone, Navigation, User, Search, Truck, Map } from 'lucide-react';
import { DriverMap, DriverList } from './DriverAvailability';
import { mockDrivers } from '../data/mockDrivers';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';

interface ServiceRequest {
  id: string;
  clientName: string;
  clientPhone: string;
  location: { lat: number; lng: number; address: string };
  serviceType: string;
  vehicleType: string;
  status: 'pending' | 'assigned' | 'en-route' | 'arrived' | 'completed';
  priority: 'emergency' | 'high' | 'normal';
  requestedAt: Date;
  assignedDriver?: string;
  eta?: number;
  description?: string;
}

const mockRequests: ServiceRequest[] = [
  {
    id: 'REQ-8472',
    clientName: 'Sarah Williams',
    clientPhone: '(555) 234-5678',
    location: { lat: 40.7128, lng: -74.0060, address: 'I-95 Exit 15, Near Mile Marker 42' },
    serviceType: 'Emergency Towing',
    vehicleType: 'Sedan',
    status: 'pending',
    priority: 'emergency',
    requestedAt: new Date(Date.now() - 2 * 60000),
    description: 'Vehicle broke down, smoke from engine',
  },
  {
    id: 'REQ-8471',
    clientName: 'John Martinez',
    clientPhone: '(555) 345-6789',
    location: { lat: 40.7500, lng: -74.0300, address: '123 Main St, Downtown' },
    serviceType: 'Flat Tire',
    vehicleType: 'SUV',
    status: 'en-route',
    priority: 'high',
    requestedAt: new Date(Date.now() - 15 * 60000),
    assignedDriver: 'Mike Johnson',
    eta: 8,
  },
  {
    id: 'REQ-8470',
    clientName: 'Emily Chen',
    clientPhone: '(555) 456-7890',
    location: { lat: 40.7200, lng: -74.0100, address: 'Oak Avenue & 5th Street' },
    serviceType: 'Dead Battery',
    vehicleType: 'Sedan',
    status: 'assigned',
    priority: 'normal',
    requestedAt: new Date(Date.now() - 20 * 60000),
    assignedDriver: 'David Brown',
  },
  {
    id: 'REQ-8469',
    clientName: 'Michael Davis',
    clientPhone: '(555) 567-8901',
    location: { lat: 40.7400, lng: -74.0200, address: 'Highway 9, Mile 23' },
    serviceType: 'Accident Recovery',
    vehicleType: 'Truck',
    status: 'arrived',
    priority: 'emergency',
    requestedAt: new Date(Date.now() - 35 * 60000),
    assignedDriver: 'Sarah Thompson',
    description: 'Minor collision, vehicle not drivable',
  },
  {
    id: 'REQ-8468',
    clientName: 'Lisa Anderson',
    clientPhone: '(555) 678-9012',
    location: { lat: 40.7300, lng: -74.0150, address: 'Shopping Center Parking Lot' },
    serviceType: 'Vehicle Lockout',
    vehicleType: 'Van',
    status: 'completed',
    priority: 'normal',
    requestedAt: new Date(Date.now() - 60 * 60000),
    assignedDriver: 'Tom Wilson',
  },
];

export function ServiceDashboard() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTab, setSelectedTab] = useState('all');

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'emergency':
        return 'bg-red-600';
      case 'high':
        return 'bg-orange-600';
      default:
        return 'bg-blue-600';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'secondary';
      case 'assigned':
        return 'default';
      case 'en-route':
        return 'default';
      case 'arrived':
        return 'default';
      case 'completed':
        return 'secondary';
      default:
        return 'secondary';
    }
  };

  const filterRequests = (requests: ServiceRequest[]) => {
    let filtered = requests;

    if (selectedTab !== 'all') {
      if (selectedTab === 'emergency') {
        filtered = filtered.filter(r => r.priority === 'emergency');
      } else {
        filtered = filtered.filter(r => r.status === selectedTab);
      }
    }

    if (searchQuery) {
      filtered = filtered.filter(r => 
        r.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.clientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.location.address.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    return filtered;
  };

  const filteredRequests = filterRequests(mockRequests);

  const stats = {
    total: mockRequests.length,
    pending: mockRequests.filter(r => r.status === 'pending').length,
    active: mockRequests.filter(r => r.status === 'assigned' || r.status === 'en-route').length,
    emergency: mockRequests.filter(r => r.priority === 'emergency').length,
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="border-b bg-white">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                <Truck className="size-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl">Service Dashboard</h1>
                <p className="text-sm text-muted-foreground">Monitor and manage service requests</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Dialog>
                <DialogTrigger asChild>
                  <Button variant="outline">
                    <Map className="mr-2 size-4" />
                    Driver Availability
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle>Driver Availability & Locations</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-6 mt-4">
                    <DriverMap drivers={mockDrivers} />
                    <Card>
                      <CardHeader>
                        <CardTitle>Driver List</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <DriverList drivers={mockDrivers} />
                      </CardContent>
                    </Card>
                  </div>
                </DialogContent>
              </Dialog>
              <Button onClick={() => navigate('/')} variant="outline">
                Client View →
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-6 max-w-7xl">
        {/* Stats */}
        <div className="grid md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Total Requests</p>
                  <p className="text-3xl font-semibold mt-1">{stats.total}</p>
                </div>
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                  <MapPin className="size-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Pending</p>
                  <p className="text-3xl font-semibold mt-1">{stats.pending}</p>
                </div>
                <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center">
                  <Clock className="size-6 text-yellow-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Active</p>
                  <p className="text-3xl font-semibold mt-1">{stats.active}</p>
                </div>
                <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
                  <Navigation className="size-6 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-red-700">Emergencies</p>
                  <p className="text-3xl font-semibold mt-1 text-red-900">{stats.emergency}</p>
                </div>
                <div className="w-12 h-12 bg-red-200 rounded-full flex items-center justify-center">
                  <AlertCircle className="size-6 text-red-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Search and Filters */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex gap-4 items-center">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  placeholder="Search by request ID, client name, or location..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Requests List */}
        <Card>
          <CardHeader>
            <CardTitle>Service Requests</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs value={selectedTab} onValueChange={setSelectedTab}>
              <TabsList className="mb-4">
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="emergency">Emergency</TabsTrigger>
                <TabsTrigger value="pending">Pending</TabsTrigger>
                <TabsTrigger value="en-route">En Route</TabsTrigger>
                <TabsTrigger value="completed">Completed</TabsTrigger>
              </TabsList>

              <TabsContent value={selectedTab} className="mt-0">
                <div className="space-y-4">
                  {filteredRequests.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                      <MapPin className="size-12 mx-auto mb-3 opacity-20" />
                      <p>No requests found</p>
                    </div>
                  ) : (
                    filteredRequests.map((request) => (
                      <div
                        key={request.id}
                        className="border rounded-lg p-4 hover:bg-gray-50 transition-colors cursor-pointer"
                        onClick={() => navigate(`/service/${request.id}`)}
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-start gap-3">
                            <div className={`w-1 h-16 rounded-full ${getPriorityColor(request.priority)}`}></div>
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-semibold">{request.id}</span>
                                <Badge variant={getStatusColor(request.status)}>
                                  {request.status.replace('-', ' ')}
                                </Badge>
                                {request.priority === 'emergency' && (
                                  <Badge className="bg-red-600">EMERGENCY</Badge>
                                )}
                              </div>
                              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                <span className="flex items-center gap-1">
                                  <User className="size-3" />
                                  {request.clientName}
                                </span>
                                <span className="flex items-center gap-1">
                                  <Phone className="size-3" />
                                  {request.clientPhone}
                                </span>
                                <span className="flex items-center gap-1">
                                  <Clock className="size-3" />
                                  {Math.floor((Date.now() - request.requestedAt.getTime()) / 60000)} min ago
                                </span>
                              </div>
                            </div>
                          </div>

                          {request.eta && request.status === 'en-route' && (
                            <div className="text-right">
                              <div className="text-sm font-medium text-green-600">ETA: {request.eta} min</div>
                            </div>
                          )}
                        </div>

                        <div className="grid md:grid-cols-2 gap-4 pl-4">
                          <div>
                            <div className="flex items-start gap-2 mb-2">
                              <MapPin className="size-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                              <div>
                                <p className="text-sm font-medium">Location</p>
                                <p className="text-sm text-muted-foreground">{request.location.address}</p>
                                <p className="text-xs text-muted-foreground">
                                  {request.location.lat.toFixed(4)}°N, {Math.abs(request.location.lng).toFixed(4)}°W
                                </p>
                              </div>
                            </div>
                          </div>

                          <div>
                            <div className="flex items-start gap-2">
                              <Truck className="size-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                              <div>
                                <p className="text-sm font-medium">Service</p>
                                <p className="text-sm text-muted-foreground">
                                  {request.serviceType} - {request.vehicleType}
                                </p>
                                {request.assignedDriver && (
                                  <p className="text-xs text-muted-foreground mt-1">
                                    Driver: {request.assignedDriver}
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>

                        {request.description && (
                          <div className="mt-3 pl-4 pt-3 border-t">
                            <p className="text-sm text-muted-foreground">
                              <span className="font-medium">Note:</span> {request.description}
                            </p>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}