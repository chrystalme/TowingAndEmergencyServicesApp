'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { MapPin, Truck, AlertCircle, Loader2, User, Phone, Navigation } from 'lucide-react';
import { toast } from 'sonner';
import apiClient from '@/lib/api';

const requestSchema = z.object({
  serviceType: z.enum(['towing', 'roadside', 'recovery'], { required_error: 'Please select a service type' }),
  vehicleType: z.enum(['car', 'suv', 'truck', 'motorcycle', 'other'], { required_error: 'Please select a vehicle type' }),
  description: z.string().min(10, 'Please provide more details (at least 10 characters)'),
  location: z.string().min(5, 'Please provide a valid location'),
  name: z.string().min(2, 'Please enter your name'),
  phoneNumber: z.string().min(10, 'Please provide a valid phone number'),
});

type RequestForm = z.infer<typeof requestSchema>;

const serviceTypes = [
  { value: 'towing', label: 'Emergency Towing' },
  { value: 'roadside', label: 'Roadside Assistance' },
  { value: 'recovery', label: 'Vehicle Recovery' },
] as const;

const vehicleTypes = [
  { value: 'car', label: 'Car/Sedan' },
  { value: 'suv', label: 'SUV/Crossover' },
  { value: 'truck', label: 'Truck/Van' },
  { value: 'motorcycle', label: 'Motorcycle' },
  { value: 'other', label: 'Other' },
] as const;

export default function RequestPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [gettingLocation, setGettingLocation] = useState(false);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [dispatchResult, setDispatchResult] = useState<any>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    setValue,
  } = useForm<RequestForm>({
    resolver: zodResolver(requestSchema),
    mode: 'onChange',
    defaultValues: {
      serviceType: 'towing',
      vehicleType: 'car',
    },
  });

  const handleGetLocation = async () => {
    setGettingLocation(true);
    try {
      if (!navigator.geolocation) {
        toast.error('Geolocation is not supported by your browser');
        return;
      }

      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0,
        });
      });

      const { latitude, longitude } = position.coords;
      setCoords({ lat: latitude, lng: longitude });
      // Reverse geocode to get address
      try {
        const response = await fetch(
          `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&addressdetails=1`
        );
        const data = await response.json();
        const address = data.display_name || `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
        setValue('location', address);
        toast.success('Location detected');
      } catch {
        setValue('location', `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`);
        toast.success('Coordinates captured');
      }
    } catch (error) {
      if (error instanceof GeolocationPositionError) {
        if (error.code === error.PERMISSION_DENIED) {
          toast.error('Location permission denied. Please enter manually.');
        } else {
          toast.error('Unable to get location. Please enter manually.');
        }
      }
    } finally {
      setGettingLocation(false);
    }
  };

  const onSubmit = async (data: RequestForm) => {
    setIsLoading(true);
    setDispatchResult(null);
    try {
      const token = localStorage.getItem('access_token');

      if (!token) {
        toast.error('Please log in to request service');
        router.push('/login');
        return;
      }

      // Map the camelCase form fields to the API's snake_case contract and
      // attach the numeric coordinates captured when the user shared location.
      const payload = {
        service_type: data.serviceType,
        vehicle_type: data.vehicleType,
        name: data.name,
        phone_number: data.phoneNumber,
        description: data.description,
        location: data.location,
        latitude: coords?.lat ?? null,
        longitude: coords?.lng ?? null,
      };

      const created = await apiClient.createServiceRequest(payload);

      // Route the nearest available driver to this situation.
      try {
        const matched = await apiClient.createDispatch(created.id);
        setDispatchResult(matched.dispatch);
        toast.success('Nearest driver dispatched to you!');
      } catch (dispatchError: any) {
        // Either no driver is online yet, or the request lacked coordinates.
        const detail =
          dispatchError?.response?.data?.detail ?? 'No driver currently available.';
        setDispatchResult(null);
        toast.info(`Request saved — ${detail}`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Request failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        {/* Back Button */}
        <button
          onClick={() => router.back()}
          className="mb-6 inline-flex items-center text-gray-600 hover:text-gray-900 transition-colors"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>

        {/* Page Title */}
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Request Service</h1>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-8" noValidate>
          {/* Location Section */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <MapPin className="w-5 h-5 text-primary-700 mr-2" />
              Location
            </h2>

            <div className="flex gap-3 mb-4">
              <button
                type="button"
                onClick={handleGetLocation}
                disabled={gettingLocation}
                className="btn-secondary flex items-center gap-2"
              >
                <MapPin className="w-4 h-4" />
                {gettingLocation ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Getting Location...
                  </>
                ) : (
                  'Share Current Location'
                )}
              </button>
            </div>

            <div>
              <label htmlFor="location" className="sr-only">Address or Landmark</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  id="location"
                  {...register('location')}
                  className={`w-full pl-10 pr-3 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white text-gray-900 placeholder:text-gray-400 ${
                    errors.location ? 'border-red-500' : 'border-gray-300'
                  }`}
                  placeholder="Address or Landmark (Optional)"
                />
              </div>
              {errors.location && (
                <p className="mt-1 text-sm text-red-600">{errors.location.message}</p>
              )}
            </div>
          </section>

          {/* Service Details Section */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Truck className="w-5 h-5 text-primary-700 mr-2" />
              Service Details
            </h2>

            <div className="space-y-4">
              {/* Service Type */}
              <div>
                <label htmlFor="serviceType" className="block text-sm font-medium text-gray-700 mb-2">
                  Service Type <span className="text-red-500">*</span>
                </label>
                <select
                  id="serviceType"
                  {...register('serviceType')}
                  className={`w-full px-3 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white text-gray-900 ${
                    errors.serviceType ? 'border-red-500' : 'border-gray-300'
                  }`}
                >
                  <option value="">Select service type</option>
                  {serviceTypes.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
                {errors.serviceType && (
                  <p className="mt-1 text-sm text-red-600">{errors.serviceType.message}</p>
                )}
              </div>

              {/* Vehicle Type */}
              <div>
                <label htmlFor="vehicleType" className="block text-sm font-medium text-gray-700 mb-2">
                  Vehicle Type <span className="text-red-500">*</span>
                </label>
                <select
                  id="vehicleType"
                  {...register('vehicleType')}
                  className={`w-full px-3 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white text-gray-900 ${
                    errors.vehicleType ? 'border-red-500' : 'border-gray-300'
                  }`}
                >
                  <option value="">Select vehicle type</option>
                  {vehicleTypes.map((v) => (
                    <option key={v.value} value={v.value}>{v.label}</option>
                  ))}
                </select>
                {errors.vehicleType && (
                  <p className="mt-1 text-sm text-red-600">{errors.vehicleType.message}</p>
                )}
              </div>

              {/* Description */}
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
                  Description <span className="text-red-500">*</span>
                </label>
                <textarea
                  id="description"
                  {...register('description')}
                  rows={4}
                  autoFocus
                  className={`w-full px-3 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white text-gray-900 placeholder:text-gray-400 ${
                    errors.description ? 'border-red-500' : 'border-gray-300'
                  }`}
                  placeholder="Describe the issue, vehicle condition, and any special instructions..."
                />
                {errors.description && (
                  <p className="mt-1 text-sm text-red-600">{errors.description.message}</p>
                )}
              </div>
            </div>
          </section>

          {/* Contact Information Section */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <User className="w-5 h-5 text-primary-700 mr-2" />
              Contact Information
            </h2>

            <div className="space-y-4">
              {/* Name */}
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                  Name <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    id="name"
                    type="text"
                    {...register('name')}
                    className={`w-full pl-10 pr-3 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white text-gray-900 placeholder:text-gray-400 ${
                      errors.name ? 'border-red-500' : 'border-gray-300'
                    }`}
                    placeholder="Your full name"
                  />
                </div>
                {errors.name && (
                  <p className="mt-1 text-sm text-red-600">{errors.name.message}</p>
                )}
              </div>

              {/* Phone Number */}
              <div>
                <label htmlFor="phoneNumber" className="block text-sm font-medium text-gray-700 mb-2">
                  Phone Number <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    id="phoneNumber"
                    type="tel"
                    {...register('phoneNumber')}
                    className={`w-full pl-10 pr-3 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white text-gray-900 placeholder:text-gray-400 ${
                      errors.phoneNumber ? 'border-red-500' : 'border-gray-300'
                    }`}
                    placeholder="(555) 123-4567"
                  />
                </div>
                {errors.phoneNumber && (
                  <p className="mt-1 text-sm text-red-600">{errors.phoneNumber.message}</p>
                )}
              </div>
            </div>
          </section>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading || !isValid}
            className={`w-full py-3 px-4 rounded-lg text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center transition-colors ${
              isValid
                ? 'bg-primary-700 hover:bg-primary-800 focus:ring-primary-500'
                : 'bg-gray-300 cursor-not-allowed'
            }`}
          >
            {isLoading ? (
              <>
                <Loader2 className="animate-spin -ml-1 mr-2 h-5 w-5" />
                Submitting...
              </>
            ) : (
              'Submit Request'
            )}
          </button>

          {/* Dispatch result: shows the nearest driver routed to this request */}
          {dispatchResult && (
            <div className="mt-6 rounded-xl border border-green-200 bg-green-50 p-5">
              <div className="flex items-center gap-2 mb-3">
                <Navigation className="w-5 h-5 text-green-700" />
                <h3 className="font-semibold text-green-900">Driver Dispatched</h3>
              </div>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-green-700/70">Driver</dt>
                  <dd className="font-medium text-green-950">{dispatchResult.driver_email}</dd>
                </div>
                <div>
                  <dt className="text-green-700/70">Distance</dt>
                  <dd className="font-medium text-green-950">{dispatchResult.distance_km} km</dd>
                </div>
                <div>
                  <dt className="text-green-700/70">ETA</dt>
                  <dd className="font-medium text-green-950">~{dispatchResult.eta_minutes} min</dd>
                </div>
                <div>
                  <dt className="text-green-700/70">Estimated Price</dt>
                  <dd className="font-medium text-green-950">${dispatchResult.price}</dd>
                </div>
              </dl>
              <p className="mt-3 text-xs text-green-700/80">
                Status: {dispatchResult.status} · We&apos;ll keep you updated as the driver heads your way.
              </p>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}