'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Truck, MapPin, Navigation, Loader2, Wifi, WifiOff, ArrowLeft, Briefcase } from 'lucide-react';
import { toast } from 'sonner';
import apiClient from '@/lib/api';
import { formatMoney } from '@/lib/utils';

interface DriverProfile {
  id: number;
  user_id: number;
  is_online: boolean;
  current_status: string;
  current_lat?: number | null;
  current_lng?: number | null;
  last_position_at?: string | null;
}

interface Candidate {
  driver_id: number;
  email: string;
  distance_km: number;
  eta_minutes: number;
}

interface Job {
  id: number;
  status: string; // assigned | accepted | enroute | arrived
  distance_km: number;
  eta_minutes: number;
  price: number;
  currency?: string | null;
  expires_at?: string | null;
  request_location?: string | null;
  request_description?: string | null;
  request_service_type?: string | null;
}

// The one step an accepted job can move to next, and what to call it.
const NEXT_STEP: Record<string, { status: 'enroute' | 'arrived' | 'completed'; label: string }> = {
  accepted: { status: 'enroute', label: 'Start driving' },
  enroute: { status: 'arrived', label: 'I have arrived' },
  arrived: { status: 'completed', label: 'Complete job' },
};

// The API sends naive UTC timestamps (no 'Z'); without one, Date reads them as local time.
const utc = (iso: string) => new Date(/([zZ]|[+-]\d\d:\d\d)$/.test(iso) ? iso : iso + 'Z');

// Offers lapse server-side; re-check often enough that one is seen in time.
const JOB_POLL_MS = 5000;

export default function DriverConsolePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<DriverProfile | null>(null);
  const [gettingLocation, setGettingLocation] = useState(false);
  const [locatingForGoOnline, setLocatingForGoOnline] = useState(false);
  const [nearby, setNearby] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busyJobId, setBusyJobId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);

  const loadProfile = async () => {
    try {
      const data = await apiClient.getMyDriverProfile();
      setProfile(data);
    } catch {
      // 404 means the driver hasn't gone online yet — that's fine.
      setProfile(null);
    } finally {
      setIsLoading(false);
    }
  };

  const loadJobs = useCallback(async () => {
    try {
      setJobs(await apiClient.getMyDispatches());
    } catch {
      // Not a driver yet, or a transient failure: the next poll retries.
    }
  }, []);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      router.push('/login');
      return;
    }
    loadProfile();
    loadJobs();
    const timer = setInterval(loadJobs, JOB_POLL_MS);
    return () => clearInterval(timer);
  }, [router, loadJobs]);

  const capturePosition = (): Promise<{ lat: number; lng: number }> =>
    new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error('Geolocation is not supported by your browser'));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
        (err) => reject(new Error(err.message)),
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    });

  const handleShareLocation = async () => {
    setGettingLocation(true);
    try {
      const c = await capturePosition();
      setCoords(c);
      toast.success(`Location captured: ${c.lat.toFixed(5)}, ${c.lng.toFixed(5)}`);
    } catch (e: any) {
      toast.error(e.message ?? 'Unable to get location');
    } finally {
      setGettingLocation(false);
    }
  };

  const handleGoOnline = async () => {
    setLocatingForGoOnline(true);
    try {
      let c = coords;
      if (!c) c = await capturePosition();
      const data = await apiClient.updateDriverAvailability({
        is_online: true,
        current_status: 'available',
        current_lat: c.lat,
        current_lng: c.lng,
      });
      setProfile(data);
      setCoords({ lat: data.current_lat, lng: data.current_lng });
      toast.success('You are now online and available for jobs');
      // Show who else is near the same area (ranking preview).
      const near = await apiClient.getAvailableDrivers(c.lat, c.lng);
      setNearby(near);
    } catch (e: any) {
      toast.error(e.message ?? 'Could not go online');
    } finally {
      setLocatingForGoOnline(false);
    }
  };

  const handleGoOffline = async () => {
    try {
      const data = await apiClient.updateDriverAvailability({
        is_online: false,
        current_status: 'off_duty',
      });
      setProfile(data);
      setNearby([]);
      toast.success('You are now offline');
    } catch (e: any) {
      toast.error(e.message ?? 'Could not go offline');
    }
  };

  // Every job action changes the driver's status too, so both are reloaded.
  const runJobAction = async (jobId: number, action: () => Promise<unknown>, done: string) => {
    setBusyJobId(jobId);
    try {
      await action();
      toast.success(done);
      await Promise.all([loadJobs(), loadProfile()]);
    } catch (e: any) {
      toast.error(e.response?.data?.detail ?? e.message ?? 'That did not go through');
      await loadJobs();
    } finally {
      setBusyJobId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin h-10 w-10 text-primary-600" />
      </div>
    );
  }

  // Online covers a driver on a job too: they are 'enroute', not offline, and
  // must not be offered 'Go Online' (that used to reset them to available).
  const online = !!profile?.is_online;
  const onJob = online && profile?.current_status !== 'available';
  const statusText = !online ? 'Offline' : onJob ? 'Online — on a job' : 'Online — available for dispatch';

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <Link href="/dashboard" className="mb-6 inline-flex items-center text-gray-600 hover:text-gray-900 transition-colors">
          <ArrowLeft className="w-5 h-5 mr-2" /> Back to Dashboard
        </Link>

        <div className="flex items-center gap-3 mb-8">
          <Truck className="w-8 h-8 text-primary-700" />
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Driver Console</h1>
            <p className="text-gray-500">Go online and get routed to the nearest situation.</p>
          </div>
        </div>

        {/* Online status banner */}
        <div
          className={`rounded-xl border p-5 mb-6 ${online ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-white'}`}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              {online ? (
                <Wifi className="w-5 h-5 text-green-700" />
              ) : (
                <WifiOff className="w-5 h-5 text-gray-400" />
              )}
              <span className={`font-semibold ${online ? 'text-green-900' : 'text-gray-700'}`}>{statusText}</span>
            </div>
            {online ? (
              <button onClick={handleGoOffline} disabled={onJob} className="btn-secondary" title={onJob ? 'Finish your job first' : undefined}>
                Go Offline
              </button>
            ) : (
              <button
                onClick={handleGoOnline}
                disabled={locatingForGoOnline}
                className="btn-primary flex items-center gap-2"
              >
                <Navigation className="w-4 h-4" />
                {locatingForGoOnline ? 'Locating & going online...' : 'Go Online'}
              </button>
            )}
          </div>

          <button
            onClick={handleShareLocation}
            disabled={gettingLocation}
            className="btn-secondary flex items-center gap-2"
          >
            <MapPin className="w-4 h-4" />
            {gettingLocation ? 'Locating...' : 'Share My Location'}
          </button>
          {coords && (
            <p className="mt-3 text-sm text-gray-600 font-mono">
              Position: {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)}
            </p>
          )}
          {profile?.last_position_at && (
            <p className="mt-1 text-xs text-gray-400">
              Last position update: {utc(profile.last_position_at).toLocaleString()}
            </p>
          )}
        </div>

        {/* Offers and live jobs */}
        {jobs.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden mb-6">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-primary-700" />
              <h3 className="font-semibold text-gray-900">Your jobs</h3>
            </div>
            <ul className="divide-y divide-gray-100">
              {jobs.map((job) => {
                const busy = busyJobId === job.id;
                const next = NEXT_STEP[job.status];
                return (
                  <li key={job.id} className="px-6 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="font-medium text-gray-900">
                          {job.status === 'assigned' ? 'New offer' : `Job #${job.id} · ${job.status}`}
                        </p>
                        <p className="text-sm text-gray-600 truncate">{job.request_description}</p>
                        <p className="text-sm text-gray-500 truncate">{job.request_location}</p>
                        <p className="mt-1 text-sm text-gray-500">
                          {job.distance_km} km · ~{job.eta_minutes} min · {formatMoney(job.price, job.currency)}
                        </p>
                        {job.status === 'assigned' && job.expires_at && (
                          <p className="mt-1 text-xs text-amber-700">
                            Offer expires {utc(job.expires_at).toLocaleTimeString()}
                          </p>
                        )}
                      </div>
                      <div className="flex shrink-0 gap-2">
                        {job.status === 'assigned' ? (
                          <>
                            <button
                              disabled={busy}
                              onClick={() => runJobAction(job.id, () => apiClient.respondDispatch(job.id, 'accepted'), 'Job accepted')}
                              className="btn-primary"
                            >
                              Accept
                            </button>
                            <button
                              disabled={busy}
                              onClick={() => runJobAction(job.id, () => apiClient.respondDispatch(job.id, 'declined'), 'Offer declined')}
                              className="btn-secondary"
                            >
                              Decline
                            </button>
                          </>
                        ) : (
                          next && (
                            <button
                              disabled={busy}
                              onClick={() => runJobAction(job.id, () => apiClient.advanceDispatch(job.id, next.status), `Job ${next.status}`)}
                              className="btn-primary"
                            >
                              {next.label}
                            </button>
                          )
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Nearby drivers preview */}
        {nearby.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100">
              <h3 className="font-semibold text-gray-900">Online drivers near this location</h3>
              <p className="text-sm text-gray-500">Ranked nearest-first (this is the pool dispatches match from).</p>
            </div>
            <ul className="divide-y divide-gray-100">
              {nearby.map((c, i) => (
                <li key={c.driver_id} className="px-6 py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-xs font-bold">
                      {i + 1}
                    </span>
                    <span className="text-sm font-medium text-gray-900">{c.email}</span>
                  </div>
                  <div className="text-sm text-gray-500">
                    {c.distance_km} km · ~{c.eta_minutes} min
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
