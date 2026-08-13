'use client';
import useSWR from 'swr';
import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { getJob, passApplication, markApplied, getResumePdfUrl, type Job } from '@/lib/api';

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'overview' | 'resume' | 'contact' | 'match' | 'log' | 'outreach'>('overview');
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

  async function handlePass() {
    if (!latestApp) return;
    setActing(true);
    try {
      await passApplication(latestApp.id);
      toast.success('Job passed');
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

  // Typecast helper for job score details if they exist in full GET detail response
  const scoreDetails = (job as any).score;

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <button
          className="btn btn-outline btn-sm"
          style={{ marginBottom: 12 }}
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
              <button className="btn btn-outline btn-sm" onClick={handlePass} disabled={acting}>
                🚫 Pass
              </button>
            )}
          </div>
        </div>

        {/* Score + Status strip */}
        <div className="flex gap-2 items-center" style={{ marginTop: 12 }}>
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '6px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', fontWeight: 600 }}>MATCH SCORE</span>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 16,
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
            }`} style={{ padding: '4px 10px' }}>
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
            }`} style={{ padding: '4px 10px' }}>
              {latestApp.status.replace(/_/g, ' ')}
            </span>
          )}

          {job.is_test && (
            <span className="badge badge-red">🧪 TEST</span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs mb-4">
        {(['overview', 'resume', 'contact', 'match', 'log', 'outreach'] as const).map((t) => (
          <button
            key={t}
            className={`tab${activeTab === t ? ' active' : ''}`}
            onClick={() => setActiveTab(t)}
          >
            {t === 'overview' && '📋 Overview'}
            {t === 'resume'   && '📄 Resume'}
            {t === 'contact'  && '👤 Contact'}
            {t === 'match'    && '🎯 Match Details'}
            {t === 'log'      && '📋 Application Log'}
            {t === 'outreach' && '📨 Outreach'}
          </button>
        ))}
      </div>

      {/* ── Overview tab ─────────────────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16 }}>
          <div className="card flex flex-col gap-3">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Job Description</h3>
            <div style={{
              maxHeight: '600px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              background: 'var(--bg-surface)',
              padding: '12px',
              borderRadius: 'var(--radius)',
              border: '1px solid var(--border)',
            }}>
              {job.description_text || 'No description available.'}
            </div>
          </div>

          <div className="card flex flex-col gap-3">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Metadata</h3>
            <Field label="Title"   value={job.title} />
            <Field label="Company" value={job.company} />
            <Field label="Source"  value={job.source} />
            <Field label="URL"     value={job.url ? (
              <a href={job.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-primary)', textDecoration: 'underline' }}>
                Open Listing ↗
              </a>
            ) : '—'} />
            <Field label="Discovered" value={job.created_at ? new Date(job.created_at).toLocaleString() : '—'} />
            <Field label="Applied At" value={job.applied_at ? new Date(job.applied_at).toLocaleString() : '—'} />
          </div>
        </div>
      )}

      {/* ── Resume tab ──────────────────────────────────────────────────────── */}
      {activeTab === 'resume' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {latestResume ? (
            <>
              <div className="flex items-center justify-between" style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>Resume v{latestResume.version}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
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
                style={{ width: '100%', height: '600px', border: 'none' }}
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

      {/* ── Contact tab ──────────────────────────────────────────────────────── */}
      {activeTab === 'contact' && (
        <div className="flex flex-col gap-4">
          {(job.contacts ?? []).length === 0 ? (
            <div className="empty">
              <div className="empty-icon">👤</div>
              <div className="empty-title">No contacts found</div>
              <div className="empty-sub">Scraper did not detect high-probability public team members for this listing.</div>
            </div>
          ) : (
            job.contacts.map((c: any) => (
              <div key={c.id} className="card flex flex-col gap-3">
                <div className="flex justify-between items-center">
                  <div>
                    <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>{c.name}</h4>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{c.title} {c.company ? `@ ${c.company}` : ''}</p>
                  </div>
                  <div className="flex gap-2">
                    {c.linkedin_url && (
                      <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-xs">
                        LinkedIn ↗
                      </a>
                    )}
                    {c.email && (
                      <span className={`badge ${
                        c.email_confidence === 'verified' ? 'badge-green' :
                        c.email_confidence === 'inferred' ? 'badge-amber' : 'badge-status-neutral'
                      }`}>
                        {c.email_confidence}: {c.email}
                      </span>
                    )}
                  </div>
                </div>

                {/* Evidence Trail */}
                {c.evidence && c.evidence.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <div className="detail-label">Evidence Trail</div>
                    <div className="flex flex-col gap-2" style={{ marginTop: 4 }}>
                      {c.evidence.map((ev: any, idx: number) => (
                        <div key={idx} style={{
                          background: 'var(--bg-surface)',
                          border: '1px solid var(--border)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '8px 10px',
                          fontSize: '11px',
                        }}>
                          <div style={{ color: 'var(--text-primary)', fontWeight: 600, marginBottom: 2 }}>
                            Field: <span className="font-mono">{ev.field}</span>
                          </div>
                          <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: 4 }}>
                            "{ev.snippet}"
                          </p>
                          {ev.source_url && (
                            <a href={ev.source_url} target="_blank" rel="noopener noreferrer"
                               style={{ color: 'var(--text-primary)', textDecoration: 'underline' }}>
                              Source ↗
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Match Details tab ─────────────────────────────────────────────────── */}
      {activeTab === 'match' && (
        <div className="card flex flex-col gap-4">
          <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Match Score Breakdown</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: 12, borderRadius: 'var(--radius)' }}>
              <div className="detail-label">Overall Match Score</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: scoreColor(job.match_score) }}>
                {job.match_score != null ? `${job.match_score.toFixed(1)}%` : '—'}
              </div>
            </div>

            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: 12, borderRadius: 'var(--radius)' }}>
              <div className="detail-label">Stage 1 Embedding Score</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>
                {scoreDetails?.embedding_score != null ? `${(scoreDetails.embedding_score * 100).toFixed(1)}%` : '—'}
              </div>
            </div>

            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: 12, borderRadius: 'var(--radius)' }}>
              <div className="detail-label">Stage 2 Rerank Score</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>
                {scoreDetails?.llm_rerank_score != null ? `${(scoreDetails.llm_rerank_score * 100).toFixed(1)}%` : '—'}
              </div>
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <div className="detail-label">Scoring Rationale</div>
            <div style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              padding: 12,
              fontSize: 12,
              lineHeight: 1.6,
              color: 'var(--text-secondary)',
              whiteSpace: 'pre-wrap',
            }}>
              {scoreDetails?.rationale || 'No scoring rationale found.'}
            </div>
          </div>
        </div>
      )}

      {/* ── Application Log tab (formerly Audit) ──────────────────────────────── */}
      {activeTab === 'log' && (
        <div className="card flex flex-col gap-3">
          <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Application History</h3>
          {(job.applications ?? []).length === 0 ? (
            <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>No application records yet.</p>
          ) : (
            job.applications.map((a) => (
              <div key={a.id} style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: 12,
              }}>
                <div className="flex justify-between items-center">
                  <div className="flex gap-2 items-center">
                    <span className={`badge ${a.status === 'applied' ? 'badge-green' : 'badge-status-neutral'}`}>
                      {a.status}
                    </span>
                    <span className="badge badge-muted">{a.method}</span>
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {a.applied_at ? new Date(a.applied_at).toLocaleString() : '—'}
                  </span>
                </div>
                {a.result && (
                  <div style={{ marginTop: 8 }}>
                    <div className="detail-label">Result Payload</div>
                    <pre style={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border)',
                      padding: 8,
                      borderRadius: 'var(--radius-sm)',
                      fontSize: 11,
                      fontFamily: 'var(--font-mono)',
                      overflowX: 'auto',
                    }}>
                      {JSON.stringify(a.result, null, 2)}
                    </pre>
                  </div>
                )}
                <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Application ID: {a.id}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Outreach tab ────────────────────────────────────────────────────── */}
      {activeTab === 'outreach' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {(job.outreach_drafts ?? []).length === 0 ? (
            <div className="empty">
              <div className="empty-icon">📨</div>
              <div className="empty-title">No outreach drafts</div>
              <div className="empty-sub">LinkedIn / cold email drafts will appear here</div>
            </div>
          ) : (
            job.outreach_drafts.map((d) => (
              <div key={d.id} className="card">
                <div className="flex justify-between items-center" style={{ marginBottom: 8 }}>
                  <div className="flex gap-2 items-center">
                    <span className="badge badge-muted">{d.channel}</span>
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
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  padding: 12,
                  fontSize: 12,
                  color: 'var(--text-secondary)',
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'var(--font-sans)',
                  lineHeight: 1.5,
                }}>
                  {d.draft_text}
                </pre>
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
