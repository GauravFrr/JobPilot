'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { href: '/dashboard', icon: '⚡', label: 'Dashboard' },
  { href: '/jobs',      icon: '🗂️', label: 'Applications Board' },
  { href: '/discarded', icon: '🚫', label: 'Discarded' },
  { href: '/settings',  icon: '⚙️',  label: 'Settings' },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">🚀</div>
        <span className="sidebar-logo-text">JobPilot</span>
      </div>

      <nav className="sidebar-nav">
        <span className="nav-section-label">Navigation</span>
        {navItems.map(({ href, icon, label }) => (
          <Link
            key={href}
            href={href}
            className={`nav-link${pathname === href || pathname.startsWith(href + '/') ? ' active' : ''}`}
          >
            <span className="nav-icon">{icon}</span>
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
