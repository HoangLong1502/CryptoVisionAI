import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';
import QueryProvider from '../components/QueryProvider';
import AppNavbar from '../components/layout/AppNavbar';

export const metadata: Metadata = {
  title: 'Bot Coin AI',
  description: 'Multi-agent crypto analysis — live prices & buy/hold/sell recommendations',
};

export default function RootLayout({ children }: { readonly children: ReactNode }) {
  return (
    <html lang="en" className="min-h-full bg-[#08101e] text-slate-100 antialiased">
      <body className="min-h-screen bg-[#08101e] text-slate-100 antialiased">
        <QueryProvider>
          <AppNavbar />
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
