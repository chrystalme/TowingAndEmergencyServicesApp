import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { 
  MapPin, 
  Phone, 
  MessageSquare, 
  User, 
  Clock, 
  Truck, 
  Navigation,
  AlertCircle,
  Send,
  CheckCircle,
  Target
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from './ui/alert';
import { Separator } from './ui/separator';
import { sortDriversByProximity } from '../utils/routing';
import { mockDrivers } from '../data/mockDrivers';
import { DriverMap, DriverList } from './DriverAvailability';

interface Message {
  id: string;
  from: 'driver' | 'client' | 'dispatch';
  text: string;
  timestamp: Date;
}

export function RequestDetails() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  
  const [assignedDriver, setAssignedDriver] = useState('Mike Johnson');
  const [status, setStatus] = useState('en-route');
  const [eta, setEta] = useState('8');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      from: 'client',
      text: 'I see smoke coming from the engine. Is this dangerous?',
      timestamp: new Date(Date.now() - 10 * 60000),
    },
    {
      id: '2',
      from: 'dispatch',
      text: 'Please move to a safe location away from traffic if possible. Driver is 8 minutes away.',
      timestamp: new Date(Date.now() - 8 * 60000),
    },
    {
      id: '3',
      from: 'driver',
      text: "I'm on my way! Should be there in about 8 minutes. Stay safe!",
      timestamp: new Date(Date.now() - 5 * 60000),
    },
  ]);
  const [newMessage, setNewMessage] = useState('');
  const [emergencyMode, setEmergencyMode] = useState(false);

  const mockRequest = {
    id: requestId,
    clientName: 'Sarah Williams',
    clientPhone: '(555) 234-5678',
    location: { 
      lat: 40.7128, 
      lng: -74.0060, 
      address: 'I-95 Exit 15, Near Mile Marker 42' 
    },
    serviceType: 'Emergency Towing',
    vehicleType: 'Sedan',
    priority: 'emergency',
    requestedAt: new Date(Date.now() - 15 * 60000),
    description: 'Vehicle broke down, smoke from engine',
  };

  const handleSendMessage = () => {
    if (!newMessage.trim()) return;

    const message: Message = {
      id: Date.now().toString(),
      from: 'dispatch',
      text: newMessage,
      timestamp: new Date(),
    };

    setMessages([...messages, message]);
    setNewMessage('');
  };

  const handleAssignDriver = () => {
    setStatus('assigned');
  };

  const handleDispatchDriver = () => {
    setStatus('en-route');
  };

  const handleMarkArrived = () => {
    setStatus('arrived');
  };

  const handleCompleteRequest = () => {
    setStatus('completed');
  };

  const activateEmergencyProtocol = () => {
    setEmergencyMode(true);
    const emergencyMessage: Message = {
      id: Date.now().toString(),
      from: 'dispatch',
      text: '🚨 EMERGENCY PROTOCOL ACTIVATED - All available units notified. Emergency services contacted.',
      timestamp: new Date(),
    };
    setMessages([...messages, emergencyMessage]);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="border-b bg-white">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <Button 
                onClick={() => navigate('/service')}
                variant="ghost"
                className="mb-2"
              >
                ← Back to Dashboard
              </Button>
              <div className="flex items-center gap-3">
                <h1 className="text-xl">Request {requestId}</h1>
                <Badge className="bg-red-600">EMERGENCY</Badge>
                <Badge variant="default">{status.replace('-', ' ')}</Badge>
              </div>
            </div>
            
            {!emergencyMode && mockRequest.priority === 'emergency' && (
              <Button 
                onClick={activateEmergencyProtocol}
                className="bg-red-600 hover:bg-red-700"
              >
                <AlertCircle className="mr-2 size-4" />
                Activate Emergency Protocol
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-6 max-w-7xl">
        {emergencyMode && (
          <Alert className="mb-6 border-red-600 bg-red-50">
            <AlertCircle className="size-5 text-red-600" />
            <AlertTitle className="text-red-900">Emergency Protocol Active</AlertTitle>
            <AlertDescription className="text-red-800">
              All available units have been notified. Emergency services are on standby. Priority dispatch in effect.
            </AlertDescription>
          </Alert>
        )}

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Map and Location */}
            <Card>
              <CardHeader>
                <CardTitle>Live Location</CardTitle>
              </CardHeader>
              <CardContent>
                {/* Simulated Map */}
                <div className="relative w-full h-80 bg-gray-100 rounded-lg overflow-hidden border-2 border-gray-200 mb-4">
                  <div className="absolute inset-0 bg-gradient-to-br from-blue-100 to-green-100">
                    <svg className="w-full h-full opacity-20">
                      <defs>
                        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="gray" strokeWidth="1"/>
                        </pattern>
                      </defs>
                      <rect width="100%" height="100%" fill="url(#grid)" />
                    </svg>
                  </div>

                  {/* Client Location */}
                  <div 
                    className="absolute"
                    style={{ left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }}
                  >
                    <div className="relative">
                      <div className="absolute inset-0 bg-red-500 rounded-full animate-ping opacity-75" style={{ width: '24px', height: '24px', top: '-12px', left: '-12px' }}></div>
                      <MapPin className="size-10 text-red-600 drop-shadow-lg relative z-10" fill="currentColor" />
                      <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 bg-white px-3 py-1 rounded shadow-md text-sm whitespace-nowrap font-medium">
                        Client Location
                      </div>
                    </div>
                  </div>

                  {/* Driver Location */}
                  {status !== 'pending' && (
                    <div 
                      className="absolute"
                      style={{ left: '30%', top: '20%', transform: 'translate(-50%, -50%)' }}
                    >
                      <div className="relative">
                        <div className="bg-blue-600 rounded-full p-2 shadow-lg">
                          <Truck className="size-7 text-white" />
                        </div>
                        {status === 'en-route' && (
                          <div className="absolute -top-2 -right-2 bg-green-500 rounded-full p-1 animate-pulse">
                            <Navigation className="size-4 text-white" />
                          </div>
                        )}
                        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 bg-white px-3 py-1 rounded shadow-md text-sm whitespace-nowrap font-medium">
                          {assignedDriver}
                        </div>
                      </div>
                    </div>
                  )}

                  {status === 'en-route' && (
                    <svg className="absolute inset-0 w-full h-full pointer-events-none">
                      <line 
                        x1="50%" 
                        y1="50%" 
                        x2="30%"
                        y2="20%"
                        stroke="#2563eb" 
                        strokeWidth="3" 
                        strokeDasharray="8,8"
                        opacity="0.7"
                      />
                    </svg>
                  )}
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                    <div className="flex items-start gap-3">
                      <MapPin className="size-5 text-blue-600 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="font-medium text-blue-900 mb-1">Client Location</p>
                        <p className="text-sm text-blue-700">{mockRequest.location.address}</p>
                        <p className="text-xs text-blue-600 mt-1">
                          {mockRequest.location.lat.toFixed(6)}°N, {Math.abs(mockRequest.location.lng).toFixed(6)}°W
                        </p>
                      </div>
                    </div>
                  </div>

                  {status === 'en-route' && (
                    <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                      <div className="flex items-start gap-3">
                        <Navigation className="size-5 text-green-600 mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="font-medium text-green-900 mb-1">Driver En Route</p>
                          <p className="text-sm text-green-700">ETA: {eta} minutes</p>
                          <p className="text-xs text-green-600 mt-1">Distance: 2.4 miles</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Communication */}
            <Card>
              <CardHeader>
                <CardTitle>Communication</CardTitle>
              </CardHeader>
              <CardContent>
                {/* Messages */}
                <div className="space-y-4 mb-4 max-h-96 overflow-y-auto">
                  {messages.map((msg) => (
                    <div key={msg.id} className="flex gap-3">
                      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                        msg.from === 'driver' ? 'bg-blue-100' : 
                        msg.from === 'client' ? 'bg-gray-100' : 'bg-purple-100'
                      }`}>
                        {msg.from === 'driver' ? (
                          <Truck className="size-4 text-blue-600" />
                        ) : msg.from === 'client' ? (
                          <User className="size-4 text-gray-600" />
                        ) : (
                          <AlertCircle className="size-4 text-purple-600" />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-sm capitalize">{msg.from}</span>
                          <span className="text-xs text-muted-foreground">
                            {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <p className="text-sm bg-gray-100 rounded-lg px-3 py-2">{msg.text}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <Separator className="my-4" />

                {/* Message Input */}
                <div className="flex gap-2">
                  <Textarea
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    placeholder="Type a message to client or driver..."
                    rows={2}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                  />
                  <Button onClick={handleSendMessage} size="icon" className="h-auto">
                    <Send className="size-4" />
                  </Button>
                </div>

                <div className="grid grid-cols-2 gap-2 mt-3">
                  <Button variant="outline" size="sm">
                    <Phone className="mr-2 size-3" />
                    Call Client
                  </Button>
                  <Button variant="outline" size="sm">
                    <Phone className="mr-2 size-3" />
                    Call Driver
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Client Info */}
            <Card>
              <CardHeader>
                <CardTitle>Client Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Name</p>
                  <p className="font-medium">{mockRequest.clientName}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Phone</p>
                  <p className="font-medium">{mockRequest.clientPhone}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Requested</p>
                  <p className="font-medium">
                    {Math.floor((Date.now() - mockRequest.requestedAt.getTime()) / 60000)} minutes ago
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Service Details */}
            <Card>
              <CardHeader>
                <CardTitle>Service Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Service Type</p>
                  <p className="font-medium">{mockRequest.serviceType}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Vehicle Type</p>
                  <p className="font-medium">{mockRequest.vehicleType}</p>
                </div>
                {mockRequest.description && (
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Description</p>
                    <p className="text-sm">{mockRequest.description}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Driver Assignment */}
            <Card>
              <CardHeader>
                <CardTitle>Driver Assignment</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Smart Routing Recommendation */}
                {status === 'pending' && (
                  <Alert className="border-green-200 bg-green-50">
                    <Target className="size-4 text-green-600" />
                    <AlertTitle className="text-green-900">Closest Driver Available</AlertTitle>
                    <AlertDescription className="text-green-800">
                      {(() => {
                        const sortedDrivers = sortDriversByProximity(mockRequest.location, mockDrivers);
                        const closest = sortedDrivers.find(d => d.driver.status === 'available');
                        if (closest) {
                          return (
                            <div className="mt-2">
                              <p className="font-medium">{closest.driver.name} - {closest.driver.vehicle}</p>
                              <p className="text-sm">{closest.distance} miles away • ETA: {closest.eta} minutes</p>
                            </div>
                          );
                        }
                        return 'Calculating...';
                      })()}
                    </AlertDescription>
                  </Alert>
                )}

                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">Assign Driver</label>
                  <Select value={assignedDriver} onValueChange={setAssignedDriver}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {sortDriversByProximity(mockRequest.location, mockDrivers)
                        .filter(d => d.driver.status === 'available')
                        .map((driverData, index) => (
                          <SelectItem key={driverData.driver.id} value={driverData.driver.name}>
                            {index === 0 && '⭐ '}{driverData.driver.name} ({driverData.driver.vehicle}) - {driverData.distance}mi, {driverData.eta}min
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground mt-1">
                    ⭐ Indicates closest available driver
                  </p>
                </div>

                {status === 'en-route' && (
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">Update ETA (minutes)</label>
                    <Select value={eta} onValueChange={setEta}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="5">5 minutes</SelectItem>
                        <SelectItem value="8">8 minutes</SelectItem>
                        <SelectItem value="10">10 minutes</SelectItem>
                        <SelectItem value="15">15 minutes</SelectItem>
                        <SelectItem value="20">20 minutes</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Status Actions */}
            <Card>
              <CardHeader>
                <CardTitle>Update Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {status === 'pending' && (
                  <Button onClick={handleAssignDriver} className="w-full">
                    <User className="mr-2 size-4" />
                    Assign Driver
                  </Button>
                )}
                
                {status === 'assigned' && (
                  <Button onClick={handleDispatchDriver} className="w-full">
                    <Navigation className="mr-2 size-4" />
                    Dispatch Driver
                  </Button>
                )}

                {status === 'en-route' && (
                  <Button onClick={handleMarkArrived} className="w-full">
                    <MapPin className="mr-2 size-4" />
                    Mark as Arrived
                  </Button>
                )}

                {status === 'arrived' && (
                  <Button onClick={handleCompleteRequest} className="w-full bg-green-600 hover:bg-green-700">
                    <CheckCircle className="mr-2 size-4" />
                    Complete Request
                  </Button>
                )}

                {status === 'completed' && (
                  <Alert className="border-green-200 bg-green-50">
                    <CheckCircle className="size-4 text-green-600" />
                    <AlertDescription className="text-green-900">
                      Request completed successfully
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}