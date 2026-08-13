'use client';
import useSWR from 'swr';
import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { getJob, passApplication, markApplied, getResumePdfUrl, type Job } from '@/lib/api';

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [acting, setActing] = useState(false);
  const [resumeExpanded, setResumeExpanded] = useState(false);

  const { data: job, isLoading, mutate } = useSWR<Job>(
    id ? `/jobs/${id}` : null,
    () => getJob(id),
    { refreshInterval: 15000 }
  );

  if (isLoading) return <div className="loading-center"><div className="spinner" /></div>;
  if (!job) return (
    <div className="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 32, height: 32, margin: '0 auto 8px', opacity: 0.5 }}>
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <div className="empty-title">Job not found</div>
    </div>
  );

  const latestApp = job.applications?.[0];
  const latestResume = job.resume_versions?.[0];
  const scoreDetails = (job as any).score;

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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'applied': return 'var(--green)';
      case 'ready_to_apply': return 'var(--amber)';
      case 'applying':
      case 'tailoring': return 'var(--amber)';
      case 'discarded':
      case 'skipped': return 'var(--text-muted)';
      default: return 'var(--text-muted)';
    }
  };

  return (
    <>
      {/* Back navigation control */}
      <div style={{ marginBottom: 16 }}>
        <button
          className="btn btn-outline"
          style={{ padding: '6px 12px', fontSize: '11px', borderRadius: '9999px', cursor: 'pointer' }}
          onClick={() => router.back()}
        >
          ← Back to Board
        </button>
      </div>

      {/* Main Two-Column Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24, alignItems: 'start' }}>
        
        {/* LEFT COLUMN: Main task details, description, history */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Header Block */}
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 4 }}>
              {job.title}
            </h1>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {job.company} · {job.source}
            </p>
          </div>

          {/* Properties / Meta Strip */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 12,
            padding: '12px 0',
            borderTop: '1px solid var(--border)',
            borderBottom: '1px solid var(--border)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>Status:</span>
              <span className="flex items-center gap-1.5 font-semibold" style={{ color: latestApp ? getStatusColor(latestApp.status) : 'var(--text-primary)' }}>
                <span style={{
                  display: 'inline-block',
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: latestApp ? getStatusColor(latestApp.status) : 'var(--text-muted)'
                }} />
                {latestApp ? latestApp.status.replace(/_/g, ' ') : 'discovered'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>Match Score:</span>
              <span className="font-mono font-bold" style={{ color: scoreColor(job.match_score) }}>
                {job.match_score != null ? `${job.match_score.toFixed(1)}%` : '—'}
              </span>
            </div>

            {job.tier && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}>Tier:</span>
                <span className="badge badge-muted" style={{ fontWeight: 600 }}>Tier {job.tier}</span>
              </div>
            )}

            {job.is_test && (
              <span className="badge badge-red" style={{ fontWeight: 700 }}>TEST RECORD</span>
            )}
          </div>

          {/* Job Description Card */}
          <div className="card flex flex-col gap-3">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Job Description
            </h3>
            <div style={{
              maxHeight: '400px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
              fontSize: '12px',
              lineHeight: 1.6,
              color: 'var(--text-secondary)',
              background: 'var(--bg-surface)',
              padding: '12px',
              borderRadius: 'var(--radius)',
              border: '1px solid var(--border)',
            }}>
              {job.description_text || 'No description text parsed.'}
            </div>
          </div>

          {/* Tailored Resume Accordion */}
          <div className="card flex flex-col gap-3">
            <div className="flex justify-between items-center" style={{ cursor: 'pointer' }} onClick={() => setResumeExpanded(!resumeExpanded)}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Tailored Resume
              </h3>
              <button className="btn btn-outline btn-xs" style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '9999px' }}>
                {resumeExpanded ? 'Hide Preview' : 'Show Preview'}
              </button>
            </div>
            {latestResume ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div className="flex justify-between items-center" style={{ background: 'var(--bg-surface)', padding: '8px 12px', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                  <div>
                    <span className="font-mono text-xs font-bold" style={{ color: 'var(--text-primary)' }}>v{latestResume.version}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
                      Created {new Date(latestResume.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <a
                    href={getResumePdfUrl(job.id, latestResume.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-outline btn-xs"
                    style={{ gap: 4 }}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 10, height: 10 }}>
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    <span>Download PDF</span>
                  </a>
                </div>
                {resumeExpanded && (
                  <iframe
                    src={getResumePdfUrl(job.id, latestResume.id)}
                    style={{ width: '100%', height: '550px', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}
                    title="Resume PDF"
                  />
                )}
              </div>
            ) : (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 0' }}>
                Resume will be tailored once matching threshold qualifiers are verified.
              </div>
            )}
          </div>

          {/* Match Rationale Card */}
          <div className="card flex flex-col gap-3">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Match breakdown & rationale
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: 10, borderRadius: 'var(--radius)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Stage 1 Embedding Match</div>
                <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2, color: 'var(--text-primary)' }}>
                  {scoreDetails?.embedding_score != null ? `${(scoreDetails.embedding_score * 100).toFixed(1)}%` : '—'}
                </div>
              </div>
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: 10, borderRadius: 'var(--radius)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Stage 2 LLM Reranker</div>
                <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2, color: 'var(--text-primary)' }}>
                  {scoreDetails?.llm_rerank_score != null ? `${(scoreDetails.llm_rerank_score * 100).toFixed(1)}%` : '—'}
                </div>
              </div>
            </div>
            <div style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              padding: '12px',
              fontSize: '12px',
              lineHeight: 1.6,
              color: 'var(--text-secondary)',
              whiteSpace: 'pre-wrap',
              marginTop: 4
            }}>
              {scoreDetails?.rationale || 'Scoring logic metadata description not available.'}
            </div>
          </div>

          {/* Application History / log Card */}
          <div className="card flex flex-col gap-3">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Application History
            </h3>
            {(job.applications ?? []).length === 0 ? (
              <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>No audit history timeline events recorded.</p>
            ) : (
              <div className="table-wrap" style={{ marginTop: 4 }}>
                <table style={{ fontSize: 11 }}>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Method</th>
                      <th>Processed At</th>
                      <th>Payload Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {job.applications.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <span className={`badge ${a.status === 'applied' ? 'badge-green' : 'badge-status-neutral'}`} style={{ textTransform: 'uppercase', fontSize: '9px' }}>
                            {a.status}
                          </span>
                        </td>
                        <td><span className="font-mono text-xs">{a.method}</span></td>
                        <td>{a.applied_at ? new Date(a.applied_at).toLocaleString() : '—'}</td>
                        <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {a.result ? JSON.stringify(a.result) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

        </div>

        {/* RIGHT COLUMN: Sidebar controls, actions, members */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Actions & Details Card */}
          <section className="card flex flex-col gap-4">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
              <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Properties
              </h3>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 14, height: 14, color: 'var(--text-muted)' }}>
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </div>

            {/* Properties List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}>Status</span>
                <span className="font-semibold flex items-center gap-1" style={{ color: latestApp ? getStatusColor(latestApp.status) : 'var(--text-primary)' }}>
                  <span style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    backgroundColor: latestApp ? getStatusColor(latestApp.status) : 'var(--text-muted)'
                  }} />
                  {latestApp ? latestApp.status.replace(/_/g, ' ') : 'discovered'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}>Priority (Tier)</span>
                <span className="font-semibold">{job.tier ? `Tier ${job.tier}` : '—'}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}>Match Score</span>
                <span className="font-mono font-bold" style={{ color: scoreColor(job.match_score) }}>
                  {job.match_score != null ? `${job.match_score.toFixed(1)}%` : '—'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}>Scraped Date</span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  {job.created_at ? new Date(job.created_at).toLocaleDateString() : '—'}
                </span>
              </div>
            </div>

            {/* Quick Action Buttons */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              marginTop: 6,
              paddingTop: 14,
              borderTop: '1px solid var(--border)'
            }}>
              {latestApp?.status === 'ready_to_apply' && (
                <button
                  className="btn btn-primary btn-sm justify-center"
                  onClick={handleMarkApplied}
                  disabled={acting}
                  style={{ gap: 6, width: '100%', borderRadius: '9999px' }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 12, height: 12 }}>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <span>Mark Applied</span>
                </button>
              )}

              {latestApp?.status && !['applied', 'discarded', 'skipped'].includes(latestApp.status) && (
                <button
                  className="btn btn-outline btn-sm justify-center"
                  onClick={handlePass}
                  disabled={acting}
                  style={{ gap: 6, width: '100%', borderRadius: '9999px' }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 12, height: 12 }}>
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                  <span>Pass Role</span>
                </button>
              )}

              {job.url && (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-outline btn-sm justify-center"
                  style={{ gap: 6, width: '100%', borderRadius: '9999px' }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 12, height: 12 }}>
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                  <span>View Original Listing</span>
                </a>
              )}
            </div>
          </section>

          {/* Members / Scraped Contacts section */}
          <section className="card flex flex-col gap-3">
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Members / Contacts
            </h3>
            {(job.contacts ?? []).length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                No high-probability team members parsed for this target listing.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {job.contacts.map((c) => (
                  <div key={c.id} style={{
                    padding: 10,
                    borderRadius: 'var(--radius)',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6
                  }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>{c.name}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                        {c.title} {c.company ? `@ ${c.company}` : ''}
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {c.linkedin_url && (
                        <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-xs" style={{ fontSize: '9px', padding: '1px 6px' }}>
                          LinkedIn ↗
                        </a>
                      )}
                      {c.email && (
                        <span className={`badge ${
                          c.email_confidence === 'verified' ? 'badge-green' : 'badge-status-neutral'
                        }`} style={{ fontSize: '9px', padding: '1px 6px' }}>
                          {c.email}
                        </span>
                      )}
                    </div>

                    <button
                      className="btn btn-outline btn-xs justify-center"
                      disabled
                      style={{ opacity: 0.5, cursor: 'not-allowed', width: '100%', fontSize: '9px', marginTop: 2 }}
                    >
                      Message Contact
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

        </aside>

      </div>
    </>
  );
}
