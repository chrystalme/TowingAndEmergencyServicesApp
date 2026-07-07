import Link from 'next/link';
import { Truck, Wrench, Phone, MapPin } from 'lucide-react';

const features = [
  {
    icon: Truck,
    title: '24/7 Towing',
    description: 'Round-the-clock towing services for all vehicle types, from motorcycles to heavy-duty trucks.',
  },
  {
    icon: Wrench,
    title: 'Roadside Assistance',
    description: 'Jump starts, tire changes, fuel delivery, and lockout services wherever you are.',
  },
  {
    icon: Phone,
    title: 'Emergency Dispatch',
    description: 'One-call dispatch connects you with the nearest available service provider instantly.',
  },
  {
    icon: MapPin,
    title: 'Nationwide Coverage',
    description: 'Service network spanning across the country with 30-minute average response time.',
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen">
      {/* Hero Section */}
      <section className="relative bg-gradient-to-b from-primary-50 to-white py-20 lg:py-32">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl lg:text-6xl font-bold text-gray-900 mb-6">
              Reliable Towing & Emergency Services
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              Fast, professional, and available 24/7. We&apos;re here when you need us most.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/request"
                className="btn-primary text-lg px-8 py-3"
              >
                Request Service Now
              </Link>
              <Link
                href="/login"
                className="btn-secondary text-lg px-8 py-3"
              >
                Login to Dashboard
              </Link>
            </div>
          </div>

          {/* Stats */}
          <div className="mt-16 grid grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="text-3xl lg:text-4xl font-bold text-primary-600">15,000+</div>
              <div className="text-gray-600">Vehicles Towed</div>
            </div>
            <div className="text-center">
              <div className="text-3xl lg:text-4xl font-bold text-primary-600">30 min</div>
              <div className="text-gray-600">Avg Response Time</div>
            </div>
            <div className="text-center">
              <div className="text-3xl lg:text-4xl font-bold text-primary-600">99.2%</div>
              <div className="text-gray-600">Customer Satisfaction</div>
            </div>
            <div className="text-center">
              <div className="text-3xl lg:text-4xl font-bold text-primary-600">24/7</div>
              <div className="text-gray-600">Availability</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl lg:text-4xl font-bold text-gray-900 mb-4">
              Our Services
            </h2>
            <p className="text-xl text-gray-600">
              Comprehensive roadside solutions for every situation
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature) => (
              <div key={feature.title} className="card text-center">
                <div className="w-16 h-16 mx-auto mb-4 bg-primary-100 rounded-full flex items-center justify-center">
                  <feature.icon className="w-8 h-8 text-primary-600" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  {feature.title}
                </h3>
                <p className="text-gray-600">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-primary-600">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl lg:text-4xl font-bold text-white mb-4">
            Need Help Right Now?
          </h2>
          <p className="text-primary-100 mb-8 max-w-2xl mx-auto">
            Don&apos;t wait on the side of the road. Our dispatch team is standing by 24/7.
          </p>
          <Link
            href="/request"
            className="inline-block bg-white text-primary-600 px-8 py-3 rounded-lg font-semibold text-lg hover:bg-primary-50 transition-colors"
          >
            Request Emergency Service
          </Link>
        </div>
      </section>
    </main>
  );
}