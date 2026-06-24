// Utility functions for driver routing and distance calculation

export interface Location {
  lat: number;
  lng: number;
}

export interface Driver {
  id: string;
  name: string;
  vehicle: string;
  location: Location;
  status: 'available' | 'busy' | 'offline';
  activeRequestId?: string;
}

/**
 * Calculate distance between two coordinates using Haversine formula
 * Returns distance in miles
 */
export function calculateDistance(loc1: Location, loc2: Location): number {
  const R = 3959; // Earth's radius in miles
  const dLat = toRad(loc2.lat - loc1.lat);
  const dLon = toRad(loc2.lng - loc1.lng);
  
  const a = 
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(loc1.lat)) * Math.cos(toRad(loc2.lat)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const distance = R * c;
  
  return Math.round(distance * 10) / 10; // Round to 1 decimal place
}

function toRad(degrees: number): number {
  return degrees * (Math.PI / 180);
}

/**
 * Calculate estimated time of arrival in minutes based on distance
 * Assumes average speed of 40 mph in urban areas
 */
export function calculateETA(distance: number): number {
  const avgSpeed = 40; // mph
  const hours = distance / avgSpeed;
  const minutes = Math.ceil(hours * 60);
  return minutes;
}

/**
 * Find the closest available driver to a given location
 */
export function findClosestDriver(
  clientLocation: Location,
  drivers: Driver[],
  isEmergency: boolean = false
): { driver: Driver; distance: number; eta: number } | null {
  const availableDrivers = drivers.filter(d => d.status === 'available');
  
  if (availableDrivers.length === 0) {
    return null;
  }

  const driversWithDistance = availableDrivers.map(driver => ({
    driver,
    distance: calculateDistance(clientLocation, driver.location),
    eta: 0,
  }));

  // Sort by distance
  driversWithDistance.sort((a, b) => a.distance - b.distance);

  const closest = driversWithDistance[0];
  
  // Calculate ETA - reduce time for emergency by 20% (faster driving)
  const baseETA = calculateETA(closest.distance);
  closest.eta = isEmergency ? Math.ceil(baseETA * 0.8) : baseETA;

  return closest;
}

/**
 * Get all drivers sorted by distance from a location
 */
export function sortDriversByProximity(
  clientLocation: Location,
  drivers: Driver[]
): Array<{ driver: Driver; distance: number; eta: number }> {
  return drivers
    .map(driver => ({
      driver,
      distance: calculateDistance(clientLocation, driver.location),
      eta: calculateETA(calculateDistance(clientLocation, driver.location)),
    }))
    .sort((a, b) => a.distance - b.distance);
}
