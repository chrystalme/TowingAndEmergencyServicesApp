import { ClerkProvider } from '@clerk/nextjs';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Providers from '@/components/Providers';
import ClerkTokenSync from '@/components/ClerkTokenSync';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Towing & Emergency Services',
  description: 'Professional towing and emergency roadside assistance services',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ClerkProvider>
          <Providers>
            {children}
            <ClerkTokenSync />
          </Providers>
        </ClerkProvider>
      </body>
    </html>
  );
}