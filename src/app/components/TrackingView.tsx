import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { MapPin, Navigation, Clock, Phone, MessageSquare, User, Truck } from 'lucide-react';
import { Alert, AlertDescription } from './ui/alert';

interface Location {
  lat: number;
  lng: number;
}

interface DriverInfo {
  name: string;
  phone: string;
  vehicle: string;
  eta: number;
}

export function TrackingView() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  
  const [clientLocation] = useState<Location>({ lat: 40.7128, lng: -74.0060 });
  const [driverLocation, setDriverLocation] = useState<Location>({ lat: 40.7500, lng: -74.0300 });
  const [status, setStatus] = useState<'pending' | 'assigned' | 'en-route' | 'arrived'>('pending');
  const [driver, setDriver] = useState<DriverInfo | null>(null);
  const [messages, setMessages] = useState<Array<{ from: string; text: string; time: string }>>([]);

  useEffect(() => {
    // Simulate driver assignment
    const assignTimer = setTimeout(() => {
      setStatus('assigned');
      setDriver({
        name: 'Mike Johnson',
        phone: '(555) 987-6543',
        vehicle: 'Tow Truck #42',
        eta: 18,
      });
    }, 2000);

    // Simulate driver starting route
    const enRouteTimer = setTimeout(() => {
      setStatus('en-route');
      setMessages([
        { from: 'driver', text: "I'm on my way! Should be there in about 18 minutes.", time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
      ]);
    }, 4000);

    return () => {
      clearTimeout(assignTimer);
      clearTimeout(enRouteTimer);
    };
  }, []);

  // Simulate real-time driver location updates
  useEffect(() => {
    if (status === 'en-route') {
      const interval = setInterval(() => {
        setDriverLocation(prev => {
          // Move driver closer to client
          const latDiff = clientLocation.lat - prev.lat;
          const lngDiff = clientLocation.lng - prev.lng;
          
          return {
            lat: prev.lat + latDiff * 0.05,
            lng: prev.lng + lngDiff * 0.05,
          };
        });

        setDriver(prev => {
          if (!prev) return null;
          const newEta = Math.max(1, prev.eta - 1);
          if (newEta === 1) {
            setStatus('arrived');
          }
          return { ...prev, eta: newEta };
        });
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [status, clientLocation]);

  const getStatusBadge = () => {
    switch (status) {
      case 'pending':
        return <Badge variant="secondary">Finding Driver...</Badge>;
      case 'assigned':
        return <Badge className="bg-blue-600">Driver Assigned</Badge>;
      case 'en-route':
        return <Badge className="bg-green-600">Driver En Route</Badge>;
      case 'arrived':
        return <Badge className="bg-purple-600">Driver Arrived</Badge>;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-6 max-w-6xl">
        {/* Header */}
        <div className="mb-6">
          <Button 
            onClick={() => navigate('/')}
            variant="ghost"
            className="mb-4"
          >
            ← Home
          </Button>
          
          <div className="flex items-center justify-between mb-2">
            <h1>Request #{requestId}</h1>
            {getStatusBadge()}
          </div>
          <p className="text-muted-foreground">Real-time tracking of your service request</p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Map View */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Live Tracking</CardTitle>
              </CardHeader>
              <CardContent>
                {/* Map Container */}
                <div className="relative w-full h-96 bg-gray-100 rounded-lg overflow-hidden border-2 border-gray-200">
                  {/* Simulated Map Background */}
                  <div className="absolute inset-0 bg-gradient-to-br from-blue-100 to-green-100">
                    {/* Grid lines to simulate map */}
                    <svg className="w-full h-full opacity-20">
                      <defs>
                        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="gray" strokeWidth="1"/>
                        </pattern>
                      </defs>
                      <rect width="100%" height="100%" fill="url(#grid)" />
                    </svg>
                    
                    {/* Roads */}
                    <svg className="absolute inset-0 w-full h-full">
                      <line x1="0" y1="40%" x2="100%" y2="40%" stroke="#666" strokeWidth="3" opacity="0.3"/>
                      <line x1="60%" y1="0" x2="60%" y2="100%" stroke="#666" strokeWidth="3" opacity="0.3"/>
                    </svg>
                  </div>

                  {/* Client Location Marker */}
                  <div 
                    className="absolute"
                    style={{ 
                      left: '50%', 
                      top: '50%',
                      transform: 'translate(-50%, -50%)'
                    }}
                  >
                    <div className="relative">
                      <div className="absolute inset-0 bg-red-500 rounded-full animate-ping opacity-75" style={{ width: '20px', height: '20px', top: '-10px', left: '-10px' }}></div>
                      <MapPin className="size-8 text-red-600 drop-shadow-lg relative z-10" fill="currentColor" />
                      <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 bg-white px-2 py-1 rounded shadow-md text-xs whitespace-nowrap">
                        Your Location
                      </div>
                    </div>
                  </div>

                  {/* Driver Location Marker (when assigned) */}
                  {status !== 'pending' && (
                    <div 
                      className="absolute transition-all duration-1000 ease-linear"
                      style={{ 
                        left: `${30 + (driverLocation.lng - clientLocation.lng) * 500}%`,
                        top: `${20 + (driverLocation.lat - clientLocation.lat) * 500}%`,
                        transform: 'translate(-50%, -50%)'
                      }}
                    >
                      <div className="relative">
                        <div className="bg-blue-600 rounded-full p-2 shadow-lg">
                          <Truck className="size-6 text-white" />
                        </div>
                        {status === 'en-route' && (
                          <div className="absolute -top-2 -right-2 bg-green-500 rounded-full p-1">
                            <Navigation className="size-3 text-white" />
                          </div>
                        )}
                        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 bg-white px-2 py-1 rounded shadow-md text-xs whitespace-nowrap">
                          {driver?.name}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Route Line (when en route) */}
                  {status === 'en-route' && (
                    <svg className="absolute inset-0 w-full h-full pointer-events-none">
                      <line 
                        x1="50%" 
                        y1="50%" 
                        x2={`${30 + (driverLocation.lng - clientLocation.lng) * 500}%`}
                        y2={`${20 + (driverLocation.lat - clientLocation.lat) * 500}%`}
                        stroke="#2563eb" 
                        strokeWidth="2" 
                        strokeDasharray="5,5"
                        opacity="0.6"
                      />
                    </svg>
                  )}
                </div>

                {/* Location Info */}
                <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <div className="flex items-start gap-3">
                    <MapPin className="size-5 text-blue-600 mt-0.5" />
                    <div>
                      <p className="font-medium text-blue-900">Your Location</p>
                      <p className="text-sm text-blue-700">
                        {clientLocation.lat.toFixed(6)}°N, {Math.abs(clientLocation.lng).toFixed(6)}°W
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Messages */}
            {messages.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Messages</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {messages.map((msg, idx) => (
                      <div key={idx} className="flex gap-3">
                        <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                          <User className="size-4 text-blue-600" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-sm">Driver</span>
                            <span className="text-xs text-muted-foreground">{msg.time}</span>
                          </div>
                          <p className="text-sm bg-gray-100 rounded-lg px-3 py-2">{msg.text}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Status Card */}
            <Card>
              <CardHeader>
                <CardTitle>Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {status === 'pending' && (
                  <Alert>
                    <Clock className="size-4" />
                    <AlertDescription>
                      We're finding the nearest available driver for you...
                    </AlertDescription>
                  </Alert>
                )}

                {status === 'arrived' && (
                  <Alert className="border-green-200 bg-green-50">
                    <MapPin className="size-4 text-green-600" />
                    <AlertDescription className="text-green-900">
                      Your driver has arrived! Look for {driver?.vehicle}.
                    </AlertDescription>
                  </Alert>
                )}

                {driver && (
                  <>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-sm">
                        <User className="size-4 text-muted-foreground" />
                        <span className="font-medium">{driver.name}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Truck className="size-4 text-muted-foreground" />
                        <span>{driver.vehicle}</span>
                      </div>
                      {status === 'en-route' && (
                        <div className="flex items-center gap-2 text-sm">
                          <Clock className="size-4 text-muted-foreground" />
                          <span>ETA: {driver.eta} minutes</span>
                        </div>
                      )}
                    </div>

                    <div className="pt-4 border-t space-y-2">
                      <Button className="w-full" variant="outline">
                        <Phone className="mr-2 size-4" />
                        Call Driver
                      </Button>
                      <Button className="w-full" variant="outline">
                        <MessageSquare className="mr-2 size-4" />
                        Send Message
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Service Info */}
            <Card>
              <CardHeader>
                <CardTitle>Service Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Request ID:</span>
                  <span className="font-medium">#{requestId}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Service Type:</span>
                  <span className="font-medium">Emergency Towing</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Vehicle:</span>
                  <span className="font-medium">Sedan</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Requested:</span>
                  <span className="font-medium">{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              </CardContent>
            </Card>

            {/* Emergency Contact */}
            <Card className="border-red-200 bg-red-50">
              <CardContent className="pt-6">
                <Button className="w-full bg-red-600 hover:bg-red-700">
                  <Phone className="mr-2 size-4" />
                  Emergency Hotline
                </Button>
                <p className="text-xs text-center text-red-700 mt-2">
                  Available 24/7: (555) 911-HELP
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
