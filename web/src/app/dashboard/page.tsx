'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Truck, Settings, LogOut, History, MapPin, Clock, CheckCircle, AlertCircle, Loader2, User, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

interface ServiceRequest {
  id: number;
  description: string;
  location: string;
  status: string;
  created_at: string;
  updated_at: string;
  requester_email?: string | null;
  driver_email?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

interface UserData {
  id: number;
  email: string;
  is_active: boolean;
}

export default function DashboardPage() {
  const router = useRouter();
  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [user, setUser] = useState<UserData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'active' | 'history'>('active');

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }

    fetchUserAndRequests(token);
  }, [router]);

  const fetchUserAndRequests = async (token: string) => {
    try {
      const [userRes, requestsRes] = await Promise.all([
        fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/users/me`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/service-requests`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
      ]);

      if (!userRes.ok || !requestsRes.ok) {
        throw new Error('Failed to fetch data');
      }

      const userData = await userRes.json();
      const requestsData = await requestsRes.json();

      setUser(userData);
      setRequests(requestsData);
    } catch (error) {
      toast.error('Failed to load dashboard');
      localStorage.removeItem('access_token');
      router.push('/login');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    router.push('/');
  };

  const refreshRequests = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    setRefreshing(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/service-requests`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to refresh');
      setRequests(await res.json());
      toast.success('Requests refreshed');
    } catch {
      toast.error('Failed to refresh requests');
    } finally {
      setRefreshing(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'assigned': return 'bg-blue-100 text-blue-800';
      case 'in_progress': return 'bg-purple-100 text-purple-800';
      case 'completed': return 'bg-green-100 text-green-800';
      case 'cancelled': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const filteredRequests = requests.filter((req) => {
    if (activeTab === 'active') {
      return !['completed', 'cancelled'].includes(req.status);
    }
    return ['completed', 'cancelled'].includes(req.status);
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin h-10 w-10 text-primary-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-8">
              <Link href="/dashboard" className="text-xl font-bold text-primary-600 flex items-center">
                <Truck className="w-7 h-7 mr-2" />
                TowAssist
              </Link>
              <nav className="hidden md:flex space-x-6">
                <button
                  onClick={() => setActiveTab('active')}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeTab === 'active'
                      ? 'bg-primary-100 text-primary-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  Active Requests
                </button>
                <button
                  onClick={() => setActiveTab('history')}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeTab === 'history'
                      ? 'bg-primary-100 text-primary-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  History
                </button>
              </nav>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-700 hidden sm:block">
                {user?.email}
              </span>
              <button
                onClick={refreshRequests}
                disabled={refreshing}
                className="p-2 rounded-lg text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors disabled:opacity-50"
                title="Refresh requests"
              >
                <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={handleLogout}
                className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Active Requests"
            value={requests.filter(r => !['completed', 'cancelled'].includes(r.status)).length}
            icon={AlertCircle}
            color="text-yellow-600 bg-yellow-100"
          />
          <StatCard
            title="Completed"
            value={requests.filter(r => r.status === 'completed').length}
            icon={CheckCircle}
            color="text-green-600 bg-green-100"
          />
          <StatCard
            title="Total Requests"
            value={requests.length}
            icon={History}
            color="text-blue-600 bg-blue-100"
          />
          <StatCard
            title="This Month"
            value={requests.filter(r => new Date(r.created_at) > new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)).length}
            icon={Clock}
            color="text-purple-600 bg-purple-100"
          />
        </div>

        {/* Requests Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Service
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Requester
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Location
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredRequests.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                      {activeTab === 'active' ? (
                        <>
                          No active requests.{' '}
                          <Link href="/request" className="text-primary-600 hover:underline">
                            Request service
                          </Link>
                        </>
                      ) : (
                        'No completed requests yet.'
                      )}
                    </td>
                  </tr>
                ) : (
                  filteredRequests.map((request) => (
                    <tr key={request.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          <Truck className="w-5 h-5 text-primary-600 mr-3" />
                          <div>
                            <p className="text-sm font-medium text-gray-900">{request.description.substring(0, 50)}...</p>
                            <p className="text-sm text-gray-500">{request.location.substring(0, 40)}...</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          <User className="w-4 h-4 text-gray-400 mr-2" />
                          <span className="text-sm text-gray-600 max-w-xs truncate">
                            {request.requester_email ?? `User #${request.id}`}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          <MapPin className="w-4 h-4 text-gray-400 mr-2" />
                          <span className="text-sm text-gray-600 max-w-xs truncate">{request.location}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(request.status)}`}>
                          {request.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {formatDate(request.created_at)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/dashboard/requests/${request.id}`}
                          className="text-sm font-medium text-primary-600 hover:text-primary-500"
                        >
                          View Details
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          <Link href="/request" className="card text-center hover:shadow-md transition-shadow">
            <Truck className="w-12 h-12 mx-auto text-primary-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Request New Service</h3>
            <p className="text-gray-600">Need immediate assistance? Request a tow or roadside help.</p>
          </Link>
          <Link href="/dashboard/vehicles" className="card text-center hover:shadow-md transition-shadow">
            <User className="w-12 h-12 mx-auto text-primary-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Manage Vehicles</h3>
            <p className="text-gray-600">Add or update your vehicle information for faster service.</p>
          </Link>
          <Link href="/dashboard/settings" className="card text-center hover:shadow-md transition-shadow">
            <Settings className="w-12 h-12 mx-auto text-primary-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Account Settings</h3>
            <p className="text-gray-600">Update your profile, notification preferences, and security.</p>
          </Link>
        </div>
      </main>
    </div>
  );
}

function StatCard({ title, value, icon: Icon, color }: { title: string; value: number; icon: React.ComponentType<{ className?: string }>; color: string }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <div className={`p-3 rounded-full ${color}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}