import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { MapPin, Phone, AlertCircle, Loader2, CheckCircle, Truck, Navigation } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from './ui/alert';
import { findClosestDriver } from '../utils/routing';
import { mockDrivers } from '../data/mockDrivers';

export function ClientRequest() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isEmergency = searchParams.get('emergency') === 'true';
  
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [address, setAddress] = useState('');
  const [isLoadingLocation, setIsLoadingLocation] = useState(false);
  const [locationConfirmed, setLocationConfirmed] = useState(false);
  const [serviceType, setServiceType] = useState(isEmergency ? 'emergency' : '');
  const [vehicleType, setVehicleType] = useState('');
  const [description, setDescription] = useState('');
  const [contactName, setContactName] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFindingDriver, setIsFindingDriver] = useState(false);
  const [matchedDriver, setMatchedDriver] = useState<{ name: string; distance: number; eta: number } | null>(null);

  const getCurrentLocation = () => {
    setIsLoadingLocation(true);
    
    // Simulate getting GPS location
    setTimeout(() => {
      const mockLat = 40.7128 + (Math.random() - 0.5) * 0.1;
      const mockLng = -74.0060 + (Math.random() - 0.5) * 0.1;
      
      setLocation({ lat: mockLat, lng: mockLng });
      setAddress(`${mockLat.toFixed(4)}°N, ${Math.abs(mockLng).toFixed(4)}°W`);
      setLocationConfirmed(true);
      setIsLoadingLocation(false);
    }, 1500);
  };

  useEffect(() => {
    if (isEmergency) {
      getCurrentLocation();
    }
  }, [isEmergency]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setIsFindingDriver(true);

    // Simulate finding the closest driver
    setTimeout(() => {
      if (location) {
        const result = findClosestDriver(location, mockDrivers, isEmergency);
        if (result) {
          setMatchedDriver({
            name: result.driver.name,
            distance: result.distance,
            eta: result.eta,
          });
        }
      }
      setIsFindingDriver(false);
      
      // Simulate request submission
      setTimeout(() => {
        const requestId = Math.random().toString(36).substring(7);
        navigate(`/tracking/${requestId}`);
      }, 2000);
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="container mx-auto px-4 py-8 max-w-2xl">
        {/* Header */}
        <div className="mb-6">
          <Button 
            onClick={() => navigate('/')}
            variant="ghost"
            className="mb-4"
          >
            ← Back
          </Button>
          
          {isEmergency && (
            <Alert className="mb-6 border-red-200 bg-red-50">
              <AlertCircle className="size-4 text-red-600" />
              <AlertTitle className="text-red-600">Emergency Request</AlertTitle>
              <AlertDescription>
                Priority assistance is being activated. Help is on the way.
              </AlertDescription>
            </Alert>
          )}

          <h1 className="mb-2">{isEmergency ? 'Emergency Assistance' : 'Request Service'}</h1>
          <p className="text-muted-foreground">
            Share your location and provide details about your situation
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Location Section */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Location</CardTitle>
              <CardDescription>
                Share your current location for accurate assistance
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!locationConfirmed ? (
                <Button
                  type="button"
                  onClick={getCurrentLocation}
                  disabled={isLoadingLocation}
                  className="w-full"
                  variant="outline"
                >
                  {isLoadingLocation ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Getting your location...
                    </>
                  ) : (
                    <>
                      <MapPin className="mr-2 size-4" />
                      Share Current Location
                    </>
                  )}
                </Button>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
                    <CheckCircle className="size-5 text-green-600 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium text-green-900">Location Confirmed</p>
                      <p className="text-sm text-green-700 mt-1">{address}</p>
                      <p className="text-xs text-green-600 mt-1">
                        Coordinates: {location?.lat.toFixed(6)}, {location?.lng.toFixed(6)}
                      </p>
                    </div>
                  </div>
                  <Button
                    type="button"
                    onClick={getCurrentLocation}
                    variant="outline"
                    size="sm"
                    className="w-full"
                  >
                    <MapPin className="mr-2 size-3" />
                    Update Location
                  </Button>
                </div>
              )}

              <div>
                <Label htmlFor="address">Address or Landmark (Optional)</Label>
                <Input
                  id="address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="e.g., Near Exit 15 on I-95"
                />
              </div>
            </CardContent>
          </Card>

          {/* Service Details */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Service Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="serviceType">Service Type *</Label>
                <Select value={serviceType} onValueChange={setServiceType} required>
                  <SelectTrigger id="serviceType">
                    <SelectValue placeholder="Select service type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="emergency">Emergency Towing</SelectItem>
                    <SelectItem value="breakdown">Vehicle Breakdown</SelectItem>
                    <SelectItem value="accident">Accident Recovery</SelectItem>
                    <SelectItem value="flat-tire">Flat Tire</SelectItem>
                    <SelectItem value="battery">Dead Battery</SelectItem>
                    <SelectItem value="lockout">Vehicle Lockout</SelectItem>
                    <SelectItem value="fuel">Out of Fuel</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="vehicleType">Vehicle Type *</Label>
                <Select value={vehicleType} onValueChange={setVehicleType} required>
                  <SelectTrigger id="vehicleType">
                    <SelectValue placeholder="Select vehicle type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sedan">Sedan</SelectItem>
                    <SelectItem value="suv">SUV</SelectItem>
                    <SelectItem value="truck">Pickup Truck</SelectItem>
                    <SelectItem value="van">Van</SelectItem>
                    <SelectItem value="motorcycle">Motorcycle</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe your situation (optional)"
                  rows={3}
                />
              </div>
            </CardContent>
          </Card>

          {/* Contact Information */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Contact Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="contactName">Name *</Label>
                <Input
                  id="contactName"
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                  placeholder="Your name"
                  required
                />
              </div>

              <div>
                <Label htmlFor="contactPhone">Phone Number *</Label>
                <Input
                  id="contactPhone"
                  type="tel"
                  value={contactPhone}
                  onChange={(e) => setContactPhone(e.target.value)}
                  placeholder="(555) 123-4567"
                  required
                />
              </div>
            </CardContent>
          </Card>

          {/* Submit */}
          <Button
            type="submit"
            disabled={!locationConfirmed || isSubmitting}
            className="w-full h-12"
            size="lg"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 size-5 animate-spin" />
                Submitting Request...
              </>
            ) : (
              <>
                <Phone className="mr-2 size-5" />
                {isEmergency ? 'Request Emergency Assistance' : 'Submit Request'}
              </>
            )}
          </Button>

          {!locationConfirmed && (
            <p className="text-sm text-muted-foreground text-center mt-3">
              Please share your location to continue
            </p>
          )}

          {/* Driver Matching Status */}
          {isSubmitting && (
            <Card className="mt-6 border-blue-200 bg-blue-50">
              <CardContent className="pt-6">
                {isFindingDriver ? (
                  <div className="flex items-center gap-3">
                    <Loader2 className="size-5 text-blue-600 animate-spin" />
                    <div>
                      <p className="font-medium text-blue-900">Finding Nearest Operator...</p>
                      <p className="text-sm text-blue-700">Analyzing {mockDrivers.filter(d => d.status === 'available').length} available drivers in your area</p>
                    </div>
                  </div>
                ) : matchedDriver ? (
                  <div className="space-y-3">
                    <div className="flex items-start gap-3">
                      <CheckCircle className="size-5 text-green-600 mt-0.5" />
                      <div className="flex-1">
                        <p className="font-medium text-green-900">Closest Operator Found!</p>
                        <p className="text-sm text-green-700 mt-1">
                          <Truck className="inline size-3 mr-1" />
                          {matchedDriver.name} is {matchedDriver.distance} miles away
                        </p>
                        <p className="text-sm text-green-700">
                          <Navigation className="inline size-3 mr-1" />
                          Estimated arrival: {matchedDriver.eta} minutes
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 pt-2">
                      <Loader2 className="size-4 text-blue-600 animate-spin" />
                      <p className="text-sm text-blue-700">Dispatching operator to your location...</p>
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          )}
        </form>
      </div>
    </div>
  );
}