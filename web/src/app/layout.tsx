import type { Metadata } from 'next';
import './globals.css';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Toaster } from 'react-hot-toast';

export const metadata: Metadata = {
  title: 'JobPilot Dashboard',
  description: 'Personal job application automation system — command center',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <DashboardLayout>
          {children}
        </DashboardLayout>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              fontSize: '12px',
            },
            success: {
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="3" style={{ width: 14, height: 14 }}>
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              )
            },
            error: {
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="3" style={{ width: 14, height: 14 }}>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              )
            }
          }}
        />
      </body>
    </html>
  );
}
