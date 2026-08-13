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
            success: { iconTheme: { primary: 'var(--green)', secondary: 'var(--bg-surface)' } },
            error: { iconTheme: { primary: 'var(--red)', secondary: 'var(--bg-surface)' } },
          }}
        />
      </body>
    </html>
  );
}
