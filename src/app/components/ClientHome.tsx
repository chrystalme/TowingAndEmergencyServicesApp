import { useNavigate } from 'react-router';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { MapPin, Phone, Shield, Clock } from 'lucide-react';

export function ClientHome() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-full mb-4">
            <Shield className="size-8 text-white" />
          </div>
          <h1 className="mb-2">RoadGuard</h1>
          <p className="text-muted-foreground">24/7 Towing & Emergency Services</p>
        </div>

        {/* Emergency Button */}
        <Card className="mb-8 border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <Button 
              onClick={() => navigate('/request?emergency=true')}
              className="w-full h-16 bg-red-600 hover:bg-red-700 text-lg"
              size="lg"
            >
              <Phone className="mr-2 size-6" />
              Emergency Assistance
            </Button>
            <p className="text-center text-sm text-muted-foreground mt-3">
              Get immediate help in case of emergency
            </p>
          </CardContent>
        </Card>

        {/* Regular Service Request */}
        <Card className="mb-8">
          <CardContent className="pt-6">
            <Button 
              onClick={() => navigate('/request')}
              className="w-full h-14 bg-blue-600 hover:bg-blue-700"
              size="lg"
            >
              <MapPin className="mr-2 size-5" />
              Request Towing Service
            </Button>
          </CardContent>
        </Card>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardHeader>
              <MapPin className="size-8 text-blue-600 mb-2" />
              <CardTitle className="text-lg">GPS Tracking</CardTitle>
              <CardDescription>
                Real-time location tracking for complete transparency
              </CardDescription>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader>
              <Clock className="size-8 text-blue-600 mb-2" />
              <CardTitle className="text-lg">Fast Response</CardTitle>
              <CardDescription>
                Average response time under 30 minutes
              </CardDescription>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader>
              <Shield className="size-8 text-blue-600 mb-2" />
              <CardTitle className="text-lg">24/7 Available</CardTitle>
              <CardDescription>
                Round-the-clock service, always here when you need us
              </CardDescription>
            </CardHeader>
          </Card>
        </div>

        {/* Service Team Access */}
        <div className="text-center">
          <Button 
            onClick={() => navigate('/service')}
            variant="outline"
            className="text-sm"
          >
            Service Team Login →
          </Button>
        </div>
      </div>
    </div>
  );
}
