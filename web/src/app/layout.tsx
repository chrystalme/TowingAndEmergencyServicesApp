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

// Clerk is optional. Without a publishable key (fresh clone, non-Clerk
// deploy) the provider would throw on every page, so it is simply not
// rendered — the app keeps working with the email/password login only.
const clerkEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {clerkEnabled ? (
          <ClerkProvider>
            <Providers>
              {children}
              <ClerkTokenSync />
            </Providers>
          </ClerkProvider>
        ) : (
          <Providers>{children}</Providers>
        )}
      </body>
    </html>
  );
}