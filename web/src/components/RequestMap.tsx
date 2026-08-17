'use client';

import { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export interface LatLng {
  lat: number;
  lng: number;
}

interface RequestMapProps {
  client: LatLng | null;
  driver: LatLng | null;
  clientLabel?: string;
  driverLabel?: string;
  className?: string;
}

// Div-icon pins (we build the HTML ourselves so the bundler never has to locate
// Leaflet's default PNG marker assets, which break under webpack).
const makePin = (color: string) =>
  L.divIcon({
    className: 'map-pin',
    html: `<div style="width:22px;height:22px;background:${color};border:2px solid #fff;border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 1px 4px rgba(0,0,0,.45)"></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 22],
    popupAnchor: [0, -22],
  });

const CLIENT_ICON = makePin('#2563eb');
const DRIVER_ICON = makePin('#16a34a');

function AutoFit({ points }: { points: LatLng[] }) {
  const map = useMap();
  const key = points.map((p) => `${p.lat.toFixed(6)},${p.lng.toFixed(6)}`).join('|');
  useEffect(() => {
    if (points.length === 1) {
      map.setView([points[0].lat, points[0].lng], 15);
    } else if (points.length >= 2) {
      map.fitBounds(
        L.latLngBounds(points.map((p) => [p.lat, p.lng]) as [number, number][]),
        { padding: [48, 48] }
      );
    }
  }, [map, key]);
  return null;
}

export default function RequestMap({
  client,
  driver,
  clientLabel = 'Client location',
  driverLabel = 'Driver location',
  className = '',
}: RequestMapProps) {
  const points: LatLng[] = [];
  if (client) points.push(client);
  if (driver) points.push(driver);

  const center = client ?? driver ?? { lat: -1.2864, lng: 36.8172 };

  return (
    <div className={`relative w-full overflow-hidden rounded-xl border border-gray-200 ${className}`} style={{ height: 360 }}>
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={12}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%', zIndex: 0 }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <AutoFit points={points} />
        {client && (
          <Marker position={[client.lat, client.lng]} icon={CLIENT_ICON}>
            <Popup>{clientLabel}</Popup>
          </Marker>
        )}
        {driver && (
          <Marker position={[driver.lat, driver.lng]} icon={DRIVER_ICON}>
            <Popup>{driverLabel}</Popup>
          </Marker>
        )}
        {client && driver && (
          <Polyline
            positions={[
              [client.lat, client.lng],
              [driver.lat, driver.lng],
            ]}
            pathOptions={{ color: '#f59e0b', weight: 3, dashArray: '6 6' }}
          />
        )}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 z-[500] flex flex-col gap-1 rounded-lg bg-white/95 px-3 py-2 text-xs shadow-sm">
        {client && (
          <span className="flex items-center gap-2 text-gray-700">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-600" /> {clientLabel}
          </span>
        )}
        {driver && (
          <span className="flex items-center gap-2 text-gray-700">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-600" /> {driverLabel}
          </span>
        )}
        {client && driver && (
          <span className="flex items-center gap-2 text-gray-500">
            <span className="inline-block h-0.5 w-3 border-t-2 border-dashed border-amber-500" /> Route to client
          </span>
        )}
      </div>
    </div>
  );
}
