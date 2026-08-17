'use client';
import useSWR from 'swr';
import { getStats, getSourceHealth, type Stats, type SourceHealth } from '@/lib/api';
import Link from 'next/link';

function scoreColor(score: number) {
  if (score >= 80) return 'var(--green)';
  if (score >= 60) return 'var(--amber)';
  return 'var(--red)';
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useSWR<Stats>('/stats', getStats, { refreshInterval: 30000 });
  const { data: health, isLoading: healthLoading } = useSWR<SourceHealth[]>('/health', getSourceHealth, { refreshInterval: 30000 });

  const unhealthySources = (health ?? []).filter(s => s.status === 'error' || s.status === 'degraded');

  return (
    <>
      <div className="page-header flex justify-between items-center">
        <div>
          <h1 className="page-title">Weekly Summary</h1>
          <p className="page-subtitle">Pipeline overview and live system health</p>
        </div>
        <Link href="/jobs" className="btn btn-primary">
          View Board →
        </Link>
      </div>

      {/* System Health Alert Banner */}
      {unhealthySources.length > 0 && (
        <div
          className="card flex items-center justify-between gap-4"
          style={{
            background: 'var(--red-soft)',
            border: '1px solid var(--red)',
            borderRadius: 'var(--radius)',
            padding: '12px 20px',
            marginBottom: '20px',
            color: 'var(--red)',
            fontSize: '12px',
            fontWeight: 600
          }}
        >
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 18, height: 18, flexShrink: 0 }}>
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>
              Warning: {unhealthySources.length} scraper source(s) are currently degraded or offline ({unhealthySources.map(s => s.source).join(', ')}). Please verify backend logs.
            </span>
          </div>
          <a href="#health-table" className="btn btn-danger btn-xs" style={{ background: 'var(--red)', color: 'var(--bg-base)', border: 'none', padding: '4px 10px' }}>
            View Details
          </a>
        </div>
      )}

      {/* Stats Grid */}
      <div className="stats-grid">
        <StatCard
          label="Applied"
          value={statsLoading ? '—' : String(stats?.total_applied ?? 0)}
          sub="Total applications sent"
          glow="var(--green)"
        />
        <StatCard
          label="Matched"
          value={statsLoading ? '—' : String(stats?.total_matched ?? 0)}
          sub="Jobs above threshold"
          glow="var(--accent)"
        />
        <StatCard
          label="Discarded"
          value={statsLoading ? '—' : String(stats?.total_discarded ?? 0)}
          sub="Filtered out"
          glow="var(--text-muted)"
        />
        <StatCard
          label="Interviews"
          value={statsLoading ? '—' : String(stats?.interviews ?? 0)}
          sub="Callbacks received"
          glow="var(--amber)"
        />
        <StatCard
          label="Avg Match"
          value={statsLoading ? '—' : (stats?.avg_match_score != null ? `${stats.avg_match_score.toFixed(0)}%` : '—')}
          sub="Across matched jobs"
          glow={stats?.avg_match_score ? scoreColor(stats.avg_match_score) : 'var(--text-muted)'}
        />
        <StatCard
          label="Apply Rate"
          value={statsLoading ? '—' : (stats?.apply_rate != null ? `${(stats.apply_rate * 100).toFixed(1)}%` : '—')}
          sub="Matched → Applied"
          glow="var(--accent)"
        />
      </div>

      {/* Source Health */}
      <div id="health-table" className="card mb-6">
        <div className="flex items-center gap-2 mb-4">
          <h2 style={{ fontSize: 14, fontWeight: 700 }}>Source Health</h2>
        </div>
        {healthLoading ? (
          <div className="loading-center"><div className="spinner" /></div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Last Polled</th>
                  <th>Jobs (24h)</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {(health ?? []).map((s) => (
                  <tr key={s.source}>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{s.source}</td>
                    <td>
                      <span className={`badge ${s.status === 'ok' ? 'badge-green' : s.status === 'degraded' ? 'badge-amber' : 'badge-red'}`}>
                        <span className={`status-dot ${s.status === 'ok' ? 'dot-green' : s.status === 'degraded' ? 'dot-amber' : 'dot-red'}`} />
                        <span style={{ marginLeft: 4 }}>{s.status}</span>
                      </span>
                    </td>
                    <td>{s.last_polled_at ? new Date(s.last_polled_at).toLocaleString() : '—'}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {s.jobs_discovered_24h}
                    </td>
                    <td style={{ color: 'var(--red)', fontSize: 11 }}>{s.error_message ?? '—'}</td>
                  </tr>
                ))}
                {(!health || health.length === 0) && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px' }}>
                      No source data yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Sources breakdown */}
      {stats?.sources && Object.keys(stats.sources).length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <h2 style={{ fontSize: 14, fontWeight: 700 }}>Applications by Source</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {Object.entries(stats.sources).map(([src, count]) => {
              const max = Math.max(...Object.values(stats.sources));
              const pct = (count / max) * 100;
              return (
                <div key={src}>
                  <div className="flex justify-between items-center" style={{ marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{src}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)', fontWeight: 700 }}>{count}</span>
                  </div>
                  <div className="score-bar-track">
                    <div className="score-bar-fill" style={{ width: `${pct}%`, background: 'var(--accent)' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}

function StatCard({ label, value, sub, glow }: { label: string; value: string; sub: string; glow: string }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: glow }}>{value}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  );
}
