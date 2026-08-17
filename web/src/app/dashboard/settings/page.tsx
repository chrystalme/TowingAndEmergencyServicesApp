'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Truck, Loader2, User, Settings as SettingsIcon, Mail, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';

interface UserData {
  id: number;
  email: string;
  is_active: boolean;
  is_superuser?: boolean;
  created_at?: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.replace('/login');
      return;
    }
    apiClient.setToken(token);
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load profile');
        setUser(await res.json());
      })
      .catch(() => toast.error('Failed to load profile'))
      .finally(() => setIsLoading(false));
  }, [router]);

  const handleLogout = () => {
    apiClient.logout();
    toast.success('Signed out');
    router.push('/');
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
        <div className="max-w-3xl mx-auto px-4 sm:px-6 h-16 flex items-center">
          <Link href="/dashboard" className="inline-flex items-center text-gray-600 hover:text-gray-900 transition-colors">
            <ArrowLeft className="w-5 h-5 mr-2" /> Back to Dashboard
          </Link>
          <Link href="/dashboard" className="ml-6 text-xl font-bold text-primary-600 flex items-center">
            <Truck className="w-7 h-7 mr-2" /> TowAssist
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
          <SettingsIcon className="w-6 h-6 text-primary-600 mr-2" /> Account Settings
        </h1>

        {user && (
          <div className="space-y-6">
            <div className="card">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4 flex items-center">
                <User className="w-4 h-4 mr-2" /> Profile
              </h2>
              <dl className="space-y-3">
                <div className="flex items-center justify-between">
                  <dt className="text-sm text-gray-500 flex items-center"><Mail className="w-4 h-4 mr-2" /> Email</dt>
                  <dd className="text-sm font-medium text-gray-900">{user.email}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-sm text-gray-500 flex items-center"><ShieldCheck className="w-4 h-4 mr-2" /> Account</dt>
                  <dd className="text-sm font-medium text-gray-900">{user.is_active ? 'Active' : 'Inactive'}</dd>
                </div>
                {user.created_at && (
                  <div className="flex items-center justify-between">
                    <dt className="text-sm text-gray-500">Member since</dt>
                    <dd className="text-sm font-medium text-gray-900">
                      {new Date(user.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                    </dd>
                  </div>
                )}
              </dl>
            </div>

            <div className="card">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Session</h2>
              <button onClick={handleLogout} className="btn-secondary w-full">
                Sign out
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
