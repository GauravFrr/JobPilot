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

  return (
    <>
      <div className="page-header flex justify-between items-center">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Pipeline overview · live stats</p>
        </div>
        <Link href="/jobs" className="btn btn-primary">
          View Applications →
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <StatCard
          label="Applied"
          value={statsLoading ? '—' : String(stats?.total_applied ?? 0)}
          sub="Total applications sent"
          glow="var(--green)"
          icon="✅"
        />
        <StatCard
          label="Matched"
          value={statsLoading ? '—' : String(stats?.total_matched ?? 0)}
          sub="Jobs above threshold"
          glow="var(--accent)"
          icon="🎯"
        />
        <StatCard
          label="Discarded"
          value={statsLoading ? '—' : String(stats?.total_discarded ?? 0)}
          sub="Filtered out"
          glow="var(--text-muted)"
          icon="🚫"
        />
        <StatCard
          label="Interviews"
          value={statsLoading ? '—' : String(stats?.interviews ?? 0)}
          sub="Callbacks received"
          glow="var(--amber)"
          icon="📞"
        />
        <StatCard
          label="Avg Match"
          value={statsLoading ? '—' : (stats?.avg_match_score != null ? `${stats.avg_match_score.toFixed(0)}%` : '—')}
          sub="Across matched jobs"
          glow={stats?.avg_match_score ? scoreColor(stats.avg_match_score) : 'var(--text-muted)'}
          icon="📊"
        />
        <StatCard
          label="Apply Rate"
          value={statsLoading ? '—' : (stats?.apply_rate != null ? `${(stats.apply_rate * 100).toFixed(1)}%` : '—')}
          sub="Matched → Applied"
          glow="var(--blue)"
          icon="⚡"
        />
      </div>

      {/* Source Health */}
      <div className="card mb-6">
        <div className="flex items-center gap-2 mb-4">
          <span style={{ fontSize: 16 }}>🛰️</span>
          <h2 style={{ fontSize: 15, fontWeight: 700 }}>Source Health</h2>
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
                        {s.status}
                      </span>
                    </td>
                    <td>{s.last_polled_at ? new Date(s.last_polled_at).toLocaleString() : '—'}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent)' }}>
                      {s.jobs_discovered_24h}
                    </td>
                    <td style={{ color: 'var(--red)', fontSize: 12 }}>{s.error_message ?? '—'}</td>
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
            <span style={{ fontSize: 16 }}>📡</span>
            <h2 style={{ fontSize: 15, fontWeight: 700 }}>Applications by Source</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {Object.entries(stats.sources).map(([src, count]) => {
              const max = Math.max(...Object.values(stats.sources));
              const pct = (count / max) * 100;
              return (
                <div key={src}>
                  <div className="flex justify-between items-center mb-4" style={{ marginBottom: 4 }}>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{src}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent)', fontWeight: 700 }}>{count}</span>
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

function StatCard({ label, value, sub, glow, icon }: { label: string; value: string; sub: string; glow: string; icon: string }) {
  return (
    <div className="stat-card" style={{ ['--glow-color' as string]: glow }}>
      <div className="stat-label">{icon} {label}</div>
      <div className="stat-value" style={{ color: glow }}>{value}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  );
}
