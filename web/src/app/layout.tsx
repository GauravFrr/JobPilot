import type { Metadata } from 'next';
import './globals.css';
import { Sidebar } from '@/components/Sidebar';
import { Toaster } from 'react-hot-toast';

export const metadata: Metadata = {
  title: 'JobPilot Dashboard',
  description: 'Personal job application automation system — command center',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="layout">
          <Sidebar />
          <main className="main-content">
            {children}
          </main>
        </div>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              fontSize: '13px',
            },
            success: { iconTheme: { primary: 'var(--green)', secondary: 'var(--bg-elevated)' } },
            error: { iconTheme: { primary: 'var(--red)', secondary: 'var(--bg-elevated)' } },
          }}
        />
      </body>
    </html>
  );
}
