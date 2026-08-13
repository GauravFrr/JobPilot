'use client';
import useSWR from 'swr';
import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { getJob, skipApplication, markApplied, getResumePdfUrl, type Job } from '@/lib/api';

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'overview' | 'resume' | 'outreach' | 'audit'>('overview');
  const [acting, setActing] = useState(false);

  const { data: job, isLoading, mutate } = useSWR<Job>(
    id ? `/jobs/${id}` : null,
    () => getJob(id),
    { refreshInterval: 15000 }
  );

  if (isLoading) return <div className="loading-center"><div className="spinner" /></div>;
  if (!job) return <div className="empty"><div className="empty-icon">🔍</div><div className="empty-title">Job not found</div></div>;

  const latestApp = job.applications?.[0];
  const latestResume = job.resume_versions?.[0];

  async function handleSkip() {
    if (!latestApp) return;
    setActing(true);
    try {
      await skipApplication(latestApp.id, 'Skipped from dashboard');
      toast.success('Job skipped');
      mutate();
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setActing(false);
    }
  }

  async function handleMarkApplied() {
    if (!latestApp) return;
    setActing(true);
    try {
      await markApplied(latestApp.id);
      toast.success('Marked as applied');
      mutate();
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setActing(false);
    }
  }

  const scoreColor = (s: number | null) => {
    if (s == null) return 'var(--text-muted)';
    if (s >= 80) return 'var(--green)';
    if (s >= 60) return 'var(--amber)';
    return 'var(--red)';
  };

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <button
          className="btn btn-outline btn-sm"
          style={{ marginBottom: 16 }}
          onClick={() => router.back()}
        >
          ← Back
        </button>
        <div className="flex justify-between items-center">
          <div>
            <h1 className="page-title">{job.title}</h1>
            <p className="page-subtitle">{job.company} · {job.source}</p>
          </div>
          <div className="flex gap-2">
            {job.url && (
              <a href={job.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-sm">
                🔗 View Listing
              </a>
            )}
            {latestApp?.status === 'ready_to_apply' && (
              <button className="btn btn-primary btn-sm" onClick={handleMarkApplied} disabled={acting}>
                ✅ Mark Applied
              </button>
            )}
            {latestApp?.status && !['applied', 'discarded', 'skipped'].includes(latestApp.status) && (
              <button className="btn btn-danger btn-sm" onClick={handleSkip} disabled={acting}>
                🚫 Skip
              </button>
            )}
          </div>
        </div>

        {/* Score + Status strip */}
        <div className="flex gap-3 items-center" style={{ marginTop: 16 }}>
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '10px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>MATCH SCORE</span>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 22,
              fontWeight: 700,
              color: scoreColor(job.match_score),
            }}>
              {job.match_score != null ? `${job.match_score.toFixed(1)}%` : '—'}
            </span>
          </div>

          {job.tier && (
            <span className={`badge ${
              job.tier === 'A' ? 'badge-green' :
              job.tier === 'B' ? 'badge-blue' :
              job.tier === 'C' ? 'badge-amber' : 'badge-muted'
            }`} style={{ fontSize: 13, padding: '6px 14px' }}>
              Tier {job.tier}
            </span>
          )}

          {latestApp && (
            <span className={`badge ${
              latestApp.status === 'applied' ? 'badge-green' :
              latestApp.status === 'ready_to_apply' ? 'badge-amber' :
              latestApp.status === 'applying' ? 'badge-amber' :
              latestApp.status === 'tailoring' ? 'badge-blue' :
              'badge-muted'
            }`} style={{ fontSize: 13, padding: '6px 14px' }}>
              {latestApp.status.replace(/_/g, ' ')}
            </span>
          )}

          {job.is_test && (
            <span className="badge badge-red" style={{ fontSize: 11 }}>🧪 TEST</span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs mb-6" style={{ marginBottom: 20 }}>
        {(['overview', 'resume', 'outreach', 'audit'] as const).map((t) => (
          <button
            key={t}
            className={`tab${activeTab === t ? ' active' : ''}`}
            onClick={() => setActiveTab(t)}
          >
            {t === 'overview' && '📋 Overview'}
            {t === 'resume'   && '📄 Resume'}
            {t === 'outreach' && '📨 Outreach'}
            {t === 'audit'    && '🔍 Audit'}
          </button>
        ))}
      </div>

      {/* ── Overview tab ─────────────────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20 }}>
          <div className="card">
            <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>Job Details</h3>
            <Field label="Title"   value={job.title} />
            <Field label="Company" value={job.company} />
            <Field label="Source"  value={job.source} />
            <Field label="URL"     value={job.url ? (
              <a href={job.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>
                {job.url}
              </a>
            ) : '—'} />
            <Field label="Discovered" value={job.created_at ? new Date(job.created_at).toLocaleString() : '—'} />
            <Field label="Applied At" value={job.applied_at ? new Date(job.applied_at).toLocaleString() : '—'} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Contacts */}
            <div className="card">
              <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: 'var(--text-secondary)' }}>
                👤 Contacts ({job.contacts?.length ?? 0})
              </h3>
              {(job.contacts ?? []).length === 0 ? (
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>No contacts found</p>
              ) : (
                job.contacts.map((c) => (
                  <div key={c.id} style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{c.name}</div>
                    {c.linkedin_url && (
                      <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer"
                        style={{ fontSize: 12, color: 'var(--accent)' }}>
                        LinkedIn ↗
                      </a>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Resume tab ──────────────────────────────────────────────────────── */}
      {activeTab === 'resume' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {latestResume ? (
            <>
              <div className="flex items-center justify-between" style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700 }}>Resume v{latestResume.version}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Generated {new Date(latestResume.created_at).toLocaleString()}
                  </div>
                </div>
                <a
                  href={getResumePdfUrl(job.id, latestResume.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-outline btn-sm"
                >
                  ⬇ Download PDF
                </a>
              </div>
              <iframe
                src={getResumePdfUrl(job.id, latestResume.id)}
                style={{ width: '100%', height: '700px', border: 'none' }}
                title="Resume PDF"
              />
            </>
          ) : (
            <div className="empty">
              <div className="empty-icon">📄</div>
              <div className="empty-title">No tailored resume yet</div>
              <div className="empty-sub">Resume will appear here once the tailoring step completes</div>
            </div>
          )}
        </div>
      )}

      {/* ── Outreach tab ────────────────────────────────────────────────────── */}
      {activeTab === 'outreach' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {(job.outreach_drafts ?? []).length === 0 ? (
            <div className="empty">
              <div className="empty-icon">📨</div>
              <div className="empty-title">No outreach drafts</div>
              <div className="empty-sub">LinkedIn / cold email drafts will appear here</div>
            </div>
          ) : (
            job.outreach_drafts.map((d) => (
              <div key={d.id} className="card">
                <div className="flex justify-between items-center" style={{ marginBottom: 12 }}>
                  <div className="flex gap-2 items-center">
                    <span className="badge badge-blue">{d.channel}</span>
                    {d.sent
                      ? <span className="badge badge-green">✅ Sent</span>
                      : <span className="badge badge-amber">⏳ Draft</span>
                    }
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {new Date(d.created_at).toLocaleString()}
                  </span>
                </div>
                <pre style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  padding: 16,
                  fontSize: 13,
                  color: 'var(--text-secondary)',
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'var(--font-sans)',
                  lineHeight: 1.6,
                }}>
                  {d.draft_text}
                </pre>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Audit tab ───────────────────────────────────────────────────────── */}
      {activeTab === 'audit' && (
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>Application Audit Log</h3>
          {(job.applications ?? []).length === 0 ? (
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>No application records yet.</p>
          ) : (
            job.applications.map((a) => (
              <div key={a.id} style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: 14,
                marginBottom: 12,
              }}>
                <div className="flex justify-between items-center">
                  <div className="flex gap-2 items-center">
                    <span className={`badge ${a.status === 'applied' ? 'badge-green' : 'badge-muted'}`}>
                      {a.status}
                    </span>
                    <span className="badge badge-muted">{a.method}</span>
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {a.applied_at ? new Date(a.applied_at).toLocaleString() : '—'}
                  </span>
                </div>
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  ID: {a.id}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="detail-field">
      <div className="detail-label">{label}</div>
      <div className="detail-value">{value}</div>
    </div>
  );
}
