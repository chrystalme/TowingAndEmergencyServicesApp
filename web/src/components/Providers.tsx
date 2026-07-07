'use client';

import { Toaster } from 'sonner';
import { ReactNode } from 'react';

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <Toaster position="top-right" />
    </>
  );
}