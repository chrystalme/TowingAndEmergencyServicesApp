'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Truck, Loader2, Plus, Trash2, Car } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';

interface Vehicle {
  id: number;
  make: string;
  model: string;
  year: number;
  plate_number: string;
  created_at: string;
}

export default function VehiclesPage() {
  const router = useRouter();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // create form
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [year, setYear] = useState('');
  const [plate, setPlate] = useState('');

  const load = () => {
    apiClient.getVehicles().then(setVehicles).catch(() => toast.error('Failed to load vehicles'));
  };

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.replace('/login');
      return;
    }
    apiClient.setToken(token);
    apiClient.getVehicles()
      .then(setVehicles)
      .catch(() => toast.error('Failed to load vehicles'))
      .finally(() => setIsLoading(false));
  }, [router]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!make || !model || !year || !plate) {
      toast.error('Please complete all fields');
      return;
    }
    setSaving(true);
    try {
      await apiClient.createVehicle({
        make,
        model,
        year: Number(year),
        plate_number: plate.toUpperCase(),
      });
      toast.success('Vehicle added');
      setMake(''); setModel(''); setYear(''); setPlate('');
      load();
    } catch {
      toast.error('Failed to add vehicle (plate may already be registered)');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin h-10 w-10 text-primary-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-16 flex items-center">
          <Link href="/dashboard" className="inline-flex items-center text-gray-600 hover:text-gray-900 transition-colors">
            <ArrowLeft className="w-5 h-5 mr-2" /> Back to Dashboard
          </Link>
          <Link href="/dashboard" className="ml-6 text-xl font-bold text-primary-600 flex items-center">
            <Truck className="w-7 h-7 mr-2" /> TowAssist
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
          <Car className="w-6 h-6 text-primary-600 mr-2" /> My Vehicles
        </h1>

        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* Create form */}
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4 flex items-center">
              <Plus className="w-4 h-4 mr-2" /> Add a Vehicle
            </h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <input className="input-field" placeholder="Make" value={make} onChange={(e) => setMake(e.target.value)} />
                <input className="input-field" placeholder="Model" value={model} onChange={(e) => setModel(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <input className="input-field" placeholder="Year" type="number" min={1900} max={2100} value={year} onChange={(e) => setYear(e.target.value)} />
                <input className="input-field" placeholder="Plate number" value={plate} onChange={(e) => setPlate(e.target.value)} />
              </div>
              <button type="submit" disabled={saving} className="btn-primary w-full disabled:opacity-50">
                {saving ? 'Adding...' : 'Add Vehicle'}
              </button>
            </form>
          </div>

          {/* List */}
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Registered Vehicles</h2>
            {vehicles.length === 0 ? (
              <p className="text-gray-500 text-sm py-6 text-center">No vehicles yet. Add your first one.</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {vehicles.map((v) => (
                  <li key={v.id} className="py-3 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{v.make} {v.model}</p>
                      <p className="text-sm text-gray-500">{v.year} · {v.plate_number}</p>
                    </div>
                    <button
                      onClick={async () => {
                        if (!confirm(`Remove ${v.make} ${v.model}?`)) return;
                        try { await apiClient.deleteVehicle(v.id); toast.success('Vehicle removed'); load(); }
                        catch { toast.error('Failed to remove vehicle'); }
                      }}
                      className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                      title="Remove vehicle"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
