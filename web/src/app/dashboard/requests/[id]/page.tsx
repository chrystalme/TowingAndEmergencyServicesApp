'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Truck, MapPin, Clock, Loader2, User, Navigation, Tag, Route } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import { formatMoney } from '@/lib/utils';

// Leaflet touches `window`, so it must never run during SSR.
const RequestMap = dynamic(() => import('@/components/RequestMap'), { ssr: false });

interface ServiceRequest {
  id: number;
  user_id: number;
  description: string;
  location: string;
  status: string;
  created_at: string;
  updated_at: string;
  requester_email?: string | null;
  driver_email?: string | null;
  dispatch_status?: string | null;
  currency?: string | null;
  driver_lat?: number | null;
  driver_lng?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  price?: number | null;
  distance_km?: number | null;
  eta_minutes?: number | null;
}

// Valid status transitions a customer is allowed to drive.
const STATUS_ORDER = ['pending', 'assigned', 'in_progress', 'completed', 'cancelled'];

const getStatusColor = (status: string) => {
  switch (status) {
    case 'pending': return 'badge-warning';
    case 'assigned': return 'badge-primary';
    case 'in_progress': return 'badge-primary';
    case 'completed': return 'badge-success';
    case 'cancelled': return 'badge-danger';
    default: return 'badge-gray';
  }
};

const formatDate = (d: string) =>
  new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

export default function RequestDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [request, setRequest] = useState<ServiceRequest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.replace('/login');
      return;
    }
    apiClient.setToken(token);
    apiClient.getServiceRequest(id)
      .then(setRequest)
      .catch(() => {
        toast.error('Failed to load request');
        router.replace('/dashboard');
      })
      .finally(() => setIsLoading(false));
  }, [id, router]);

  const updateStatus = async (status: string) => {
    if (!request || status === request.status) return;
    setUpdating(true);
    try {
      const updated = await apiClient.updateServiceRequest(request.id, { status });
      setRequest(updated);
      toast.success(`Status updated to ${status.replace('_', ' ')}`);
    } catch {
      toast.error('Failed to update status');
    } finally {
      setUpdating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin h-10 w-10 text-primary-600" />
      </div>
    );
  }

  if (!request) return null;

  const nextStatuses = STATUS_ORDER.filter((s) => s !== request.status && s !== 'cancelled');

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 h-16 flex items-center">
          <Link href="/dashboard" className="inline-flex items-center text-gray-600 hover:text-gray-900 transition-colors">
            <ArrowLeft className="w-5 h-5 mr-2" />
            Back to Dashboard
          </Link>
          <Link href="/dashboard" className="ml-6 text-xl font-bold text-primary-600 flex items-center">
            <Truck className="w-7 h-7 mr-2" /> TowAssist
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Service Request #{request.id}</h1>
            <span className={`mt-2 inline-flex px-2.5 py-1 text-xs font-semibold rounded-full ${getStatusColor(request.status)}`}>
              {request.status.replace('_', ' ')}
            </span>
          </div>
        </div>

        <div className="space-y-6">
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Details</h2>
            <p className="text-body text-gray-900">{request.description}</p>
            <div className="mt-4 flex items-start gap-2 text-gray-600">
              <MapPin className="w-5 h-5 text-primary-600 shrink-0" />
              <span>{request.location}</span>
            </div>
          </div>

          {/* Parties involved: who requested, which driver is routed */}
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center">
              <User className="w-4 h-4 mr-2" /> People
            </h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-gray-500">Requester</dt>
                <dd className="font-medium text-gray-900">{request.requester_email ?? `User #${request.user_id}`}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Assigned driver</dt>
                <dd className="font-medium text-gray-900">
                  {request.driver_email ??
                    (request.status === 'pending' ? 'Not assigned yet' : 'None')}
                </dd>
              </div>
              {request.dispatch_status && (
                <div>
                  <dt className="text-gray-500">Dispatch</dt>
                  <dd className="font-medium text-gray-900">{request.dispatch_status}</dd>
                </div>
              )}
              {request.price != null && (
                <div>
                  <dt className="text-gray-500">Est. price</dt>
                  <dd className="font-medium text-gray-900">{formatMoney(request.price, request.currency)}</dd>
                </div>
              )}
              {request.distance_km != null && (
                <div>
                  <dt className="text-gray-500">Distance</dt>
                  <dd className="font-medium text-gray-900">{request.distance_km} km</dd>
                </div>
              )}
              {request.eta_minutes != null && (
                <div>
                  <dt className="text-gray-500">ETA</dt>
                  <dd className="font-medium text-gray-900">~{request.eta_minutes} min</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Driver-in-relation-to-client map */}
          {(request.latitude != null && request.longitude != null) && (
            <div className="card">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center">
                <Route className="w-4 h-4 mr-2" /> Live Location
              </h2>
              {request.driver_lat != null && request.driver_lng != null ? (
                <RequestMap
                  client={{ lat: request.latitude, lng: request.longitude }}
                  driver={{ lat: request.driver_lat, lng: request.driver_lng }}
                  clientLabel={`Client: ${request.requester_email ?? 'requester'}`}
                  driverLabel={`Driver: ${request.driver_email ?? 'driver'}`}
                />
              ) : (
                <RequestMap
                  client={{ lat: request.latitude, lng: request.longitude }}
                  driver={null}
                  clientLabel={`Client: ${request.requester_email ?? 'requester'}`}
                />
              )}
              <p className="mt-2 text-xs text-gray-400">
                {request.driver_lat != null && request.driver_lng != null
                  ? 'Green pin is the assigned driver; blue pin is where the client is waiting.'
                  : 'This request has no assigned driver yet — only the client location is shown.'}
              </p>
            </div>
          )}

          <div className="card">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center">
              <Clock className="w-4 h-4 mr-2" /> Timeline
            </h2>
            <div className="space-y-2 text-sm text-gray-600">
              <p>Created {formatDate(request.created_at)}</p>
              <p>Last updated {formatDate(request.updated_at)}</p>
            </div>
          </div>

          {request.status !== 'completed' && request.status !== 'cancelled' && (
            <div className="card">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Update Status</h2>
              <div className="flex flex-wrap gap-3">
                {nextStatuses.map((status) => (
                  <button
                    key={status}
                    onClick={() => updateStatus(status)}
                    disabled={updating}
                    className="btn-primary-outline capitalize disabled:opacity-50"
                  >
                    Mark {status.replace('_', ' ')}
                  </button>
                ))}
                <button
                  onClick={() => updateStatus('cancelled')}
                  disabled={updating}
                  className="px-4 py-2 rounded-lg font-medium text-red-600 border-2 border-red-200 hover:bg-red-50 transition-colors disabled:opacity-50"
                >
                  Cancel Request
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
