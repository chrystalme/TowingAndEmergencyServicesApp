import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { MapPin, Truck, Circle } from 'lucide-react';
import { Driver, Location, calculateDistance } from '../utils/routing';

interface DriverMapProps {
  drivers: Driver[];
  centerLocation?: Location;
  highlightDriverId?: string;
}

export function DriverMap({ drivers, centerLocation, highlightDriverId }: DriverMapProps) {
  const mapWidth = 600;
  const mapHeight = 400;
  
  // Convert lat/lng to map coordinates
  const latRange = { min: 40.69, max: 40.76 };
  const lngRange = { min: -74.04, max: -73.98 };
  
  const coordsToPixels = (lat: number, lng: number) => {
    const x = ((lng - lngRange.min) / (lngRange.max - lngRange.min)) * mapWidth;
    const y = ((latRange.max - lat) / (latRange.max - latRange.min)) * mapHeight;
    return { x, y };
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Driver Locations Map</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative w-full rounded-lg overflow-hidden border-2 border-gray-200" style={{ height: '400px' }}>
          {/* Map Background */}
          <div className="absolute inset-0 bg-gradient-to-br from-blue-100 to-green-100">
            <svg className="w-full h-full opacity-20">
              <defs>
                <pattern id="grid-pattern" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="gray" strokeWidth="1"/>
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid-pattern)" />
            </svg>
            
            {/* Road overlay */}
            <svg className="absolute inset-0 w-full h-full">
              <line x1="0" y1="40%" x2="100%" y2="40%" stroke="#666" strokeWidth="3" opacity="0.3"/>
              <line x1="0" y1="70%" x2="100%" y2="70%" stroke="#666" strokeWidth="3" opacity="0.3"/>
              <line x1="30%" y1="0" x2="30%" y2="100%" stroke="#666" strokeWidth="3" opacity="0.3"/>
              <line x1="70%" y1="0" x2="70%" y2="100%" stroke="#666" strokeWidth="3" opacity="0.3"/>
            </svg>
          </div>

          {/* Center location (if provided) */}
          {centerLocation && (
            <div 
              className="absolute"
              style={{
                left: `${coordsToPixels(centerLocation.lat, centerLocation.lng).x}px`,
                top: `${coordsToPixels(centerLocation.lat, centerLocation.lng).y}px`,
                transform: 'translate(-50%, -50%)'
              }}
            >
              <div className="relative">
                <div className="absolute inset-0 bg-red-500 rounded-full animate-ping opacity-75" style={{ width: '24px', height: '24px', top: '-12px', left: '-12px' }}></div>
                <MapPin className="size-8 text-red-600 drop-shadow-lg relative z-10" fill="currentColor" />
                <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 bg-white px-2 py-0.5 rounded shadow-md text-xs whitespace-nowrap font-medium">
                  Client
                </div>
                {centerLocation && drivers.length > 0 && (
                  <svg className="absolute inset-0 pointer-events-none" style={{ width: `${mapWidth}px`, height: `${mapHeight}px`, left: `-${coordsToPixels(centerLocation.lat, centerLocation.lng).x}px`, top: `-${coordsToPixels(centerLocation.lat, centerLocation.lng).y}px` }}>
                    {drivers.filter(d => d.status === 'available').map(driver => {
                      const driverPos = coordsToPixels(driver.location.lat, driver.location.lng);
                      const clientPos = coordsToPixels(centerLocation.lat, centerLocation.lng);
                      return (
                        <line
                          key={driver.id}
                          x1={clientPos.x}
                          y1={clientPos.y}
                          x2={driverPos.x}
                          y2={driverPos.y}
                          stroke={driver.id === highlightDriverId ? '#16a34a' : '#93c5fd'}
                          strokeWidth={driver.id === highlightDriverId ? '2' : '1'}
                          strokeDasharray="4,4"
                          opacity={driver.id === highlightDriverId ? '0.8' : '0.3'}
                        />
                      );
                    })}
                  </svg>
                )}
              </div>
            </div>
          )}

          {/* Driver markers */}
          {drivers.map(driver => {
            const { x, y } = coordsToPixels(driver.location.lat, driver.location.lng);
            const isHighlighted = driver.id === highlightDriverId;
            const distance = centerLocation ? calculateDistance(centerLocation, driver.location) : null;
            
            return (
              <div
                key={driver.id}
                className="absolute transition-all duration-300"
                style={{
                  left: `${x}px`,
                  top: `${y}px`,
                  transform: 'translate(-50%, -50%)',
                  zIndex: isHighlighted ? 20 : 10,
                }}
              >
                <div className="relative">
                  {isHighlighted && (
                    <div className="absolute inset-0 bg-green-500 rounded-full animate-ping opacity-75" style={{ width: '40px', height: '40px', top: '-8px', left: '-8px' }}></div>
                  )}
                  <div 
                    className={`rounded-full p-2 shadow-lg ${
                      driver.status === 'available' ? 'bg-green-600' :
                      driver.status === 'busy' ? 'bg-orange-600' : 'bg-gray-400'
                    } ${isHighlighted ? 'scale-125' : ''} transition-transform`}
                  >
                    <Truck className="size-5 text-white" />
                  </div>
                  <div className={`absolute ${isHighlighted ? '-bottom-12' : '-bottom-8'} left-1/2 -translate-x-1/2 bg-white px-2 py-1 rounded shadow-md text-xs whitespace-nowrap transition-all ${isHighlighted ? 'font-semibold border-2 border-green-500' : ''}`}>
                    {driver.name.split(' ')[0]}
                    {distance !== null && driver.status === 'available' && (
                      <div className="text-xs text-muted-foreground">{distance} mi</div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-6 mt-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-600 rounded-full"></div>
            <span>Available ({drivers.filter(d => d.status === 'available').length})</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-orange-600 rounded-full"></div>
            <span>Busy ({drivers.filter(d => d.status === 'busy').length})</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-gray-400 rounded-full"></div>
            <span>Offline ({drivers.filter(d => d.status === 'offline').length})</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface DriverListProps {
  drivers: Driver[];
  centerLocation?: Location;
  onSelectDriver?: (driverId: string) => void;
  selectedDriverId?: string;
}

export function DriverList({ drivers, centerLocation, onSelectDriver, selectedDriverId }: DriverListProps) {
  // Sort drivers by distance if center location provided
  const sortedDrivers = centerLocation
    ? [...drivers].sort((a, b) => {
        const distA = calculateDistance(centerLocation, a.location);
        const distB = calculateDistance(centerLocation, b.location);
        return distA - distB;
      })
    : drivers;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'available':
        return 'bg-green-600';
      case 'busy':
        return 'bg-orange-600';
      case 'offline':
        return 'bg-gray-400';
      default:
        return 'bg-gray-400';
    }
  };

  return (
    <div className="space-y-2">
      {sortedDrivers.map((driver, index) => {
        const distance = centerLocation ? calculateDistance(centerLocation, driver.location) : null;
        const isSelected = driver.id === selectedDriverId;
        
        return (
          <div
            key={driver.id}
            className={`p-3 border rounded-lg transition-all cursor-pointer ${
              isSelected ? 'border-green-500 bg-green-50' : 'hover:bg-gray-50'
            } ${driver.status !== 'available' ? 'opacity-60' : ''}`}
            onClick={() => onSelectDriver?.(driver.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {centerLocation && driver.status === 'available' && (
                  <div className="flex items-center justify-center w-6 h-6 bg-blue-100 rounded-full text-xs font-semibold text-blue-700">
                    {index + 1}
                  </div>
                )}
                <div className={`w-2 h-2 rounded-full ${getStatusColor(driver.status)}`}></div>
                <div>
                  <p className="font-medium text-sm">{driver.name}</p>
                  <p className="text-xs text-muted-foreground">{driver.vehicle}</p>
                </div>
              </div>
              
              <div className="text-right">
                <Badge 
                  variant={driver.status === 'available' ? 'default' : 'secondary'}
                  className={driver.status === 'available' ? 'bg-green-600' : ''}
                >
                  {driver.status}
                </Badge>
                {distance !== null && driver.status === 'available' && (
                  <p className="text-xs text-muted-foreground mt-1">{distance} miles</p>
                )}
              </div>
            </div>
            
            {driver.activeRequestId && (
              <p className="text-xs text-muted-foreground mt-2">
                Currently on: {driver.activeRequestId}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
