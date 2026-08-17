'use client';
import useSWR from 'swr';
import { useState, useEffect } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { getJob, applyApplication, passApplication, markApplied, getResumePdfUrl, getFormPreviewUrl, generateOutreachDraft, updateOutreachDraftSent, type Job } from '@/lib/api';

type TabType = 'overview' | 'resume' | 'form' | 'contact' | 'match' | 'log';

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [acting, setActing] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>(() => {
    const tab = (typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('tab') : null) as TabType | null;
    return (tab && ['overview','resume','form','contact','match','log'].includes(tab)) ? tab : 'overview';
  });
  const [expandedEvidence, setExpandedEvidence] = useState<{ [key: string]: boolean }>({});

  // Outreach draft state (per contact card within this job)
  const [draftContactId, setDraftContactId] = useState<string | null>(null);
  const [draftChannel, setDraftChannel] = useState<'linkedin' | 'email'>('linkedin');
  const [draftTone, setDraftTone] = useState<'confident' | 'warm'>('confident');
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftResult, setDraftResult] = useState<{ draft_id: string; draft_text: string; channel: string } | null>(null);
  const [draftSentMap, setDraftSentMap] = useState<{ [draftId: string]: boolean }>({});

  // Sync tab param when searchParams changes
  useEffect(() => {
    const tab = searchParams.get('tab') as TabType | null;
    if (tab && ['overview','resume','form','contact','match','log'].includes(tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

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

  async function handleApply() {
    if (!latestApp) return;
    setActing(true);
    try {
      await applyApplication(latestApp.id);
      toast.success('Application triggered asynchronously');
      mutate();
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setActing(false);
    }
  }

  async function handleApplyTierB() {
    if (!job || !latestApp) return;
    if (job.url) {
      window.open(job.url, '_blank');
    }
    await handleMarkApplied();
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

  const toggleEvidence = (contactId: string) => {
    setExpandedEvidence(prev => ({
      ...prev,
      [contactId]: !prev[contactId]
    }));
  };

  async function handleGenerateDraft(jobId: string, contactId: string) {
    setDraftContactId(contactId);
    setDraftLoading(true);
    setDraftResult(null);
    try {
      const result = await generateOutreachDraft(jobId, draftChannel, draftTone);
      setDraftResult(result);
    } catch (e: unknown) {
      toast.error('Failed to generate draft: ' + (e as Error).message);
    } finally {
      setDraftLoading(false);
    }
  }

  async function handleMarkSent(draftId: string, sent: boolean) {
    try {
      await updateOutreachDraftSent(draftId, sent);
      setDraftSentMap(prev => ({ ...prev, [draftId]: sent }));
      toast.success(sent ? 'Marked as sent ✓' : 'Unmarked as sent');
    } catch (e: unknown) {
      toast.error('Failed to update: ' + (e as Error).message);
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).then(() => toast.success('Draft copied to clipboard!'));
  }

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

        {/* LEFT COLUMN: Main content area with tab switcher */}
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

          {/* Navigation Tabs Bar */}
          <div style={{
            display: 'flex',
            gap: 4,
            borderBottom: '1px solid var(--border)',
            paddingBottom: 2,
            marginBottom: 4
          }}>
            {(() => {
              const tabs: TabType[] = ['overview', 'resume'];
              if (job.tier === 'B') {
                tabs.push('form');
              }
              tabs.push('contact', 'match', 'log');
              return tabs;
            })().map((tab) => {
              const label = tab === 'overview' ? 'Overview' :
                tab === 'resume' ? 'Resume' :
                  tab === 'form' ? 'Form Preview' :
                    tab === 'contact' ? 'Contact' :
                      tab === 'match' ? 'Match Details' : 'Application Log';
              const isActive = activeTab === tab;
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    background: 'none',
                    border: 'none',
                    borderBottom: isActive ? '2px solid var(--text-primary)' : '2px solid transparent',
                    color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                    padding: '8px 16px',
                    fontSize: '13px',
                    fontWeight: isActive ? 700 : 500,
                    cursor: 'pointer',
                    outline: 'none',
                    transition: 'all 0.15s ease',
                    marginBottom: '-1px'
                  }}
                >
                  {label}
                  {tab === 'contact' && job.contacts && job.contacts.length > 0 && (
                    <span style={{
                      marginLeft: 6,
                      fontSize: '10px',
                      background: 'var(--border)',
                      color: 'var(--text-primary)',
                      padding: '1px 5px',
                      borderRadius: '9999px',
                      fontWeight: 600
                    }}>
                      {job.contacts.length}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Tab Panes rendering */}
          {activeTab === 'overview' && (
            <div className="card flex flex-col gap-3">
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Job Description
              </h3>
              <div style={{
                maxHeight: '600px',
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                fontSize: '12px',
                lineHeight: 1.6,
                color: 'var(--text-secondary)',
                background: 'var(--bg-surface)',
                padding: '16px',
                borderRadius: 'var(--radius)',
                border: '1px solid var(--border)',
              }}>
                {job.description_text || 'No description text parsed.'}
              </div>
            </div>
          )}

          {activeTab === 'resume' && (
            <div className="card flex flex-col gap-4">
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Tailored Resume Version
              </h3>
              {latestResume ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="flex justify-between items-center" style={{ background: 'var(--bg-surface)', padding: '10px 14px', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                    <div>
                      <span className="font-mono text-xs font-bold" style={{ color: 'var(--text-primary)' }}>v{latestResume.version}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
                        Generated {new Date(latestResume.created_at).toLocaleString()} using {(latestResume as any).model_used || 'claude-sonnet-5'}
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
                  <iframe
                    src={getResumePdfUrl(job.id, latestResume.id)}
                    style={{ width: '100%', height: '650px', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}
                    title="Resume PDF"
                  />
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 0', textAlign: 'center' }}>
                  No resume tailored for this job listing. A resume version is generated when the job passes the matching threshold.
                </div>
              )}
            </div>
          )}

          {activeTab === 'form' && (
            <div className="card flex flex-col gap-4">
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Pre-Filled Form Preview
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                This is a screenshot of the pre-filled form fields before final submission. Review it carefully before clicking Apply.
              </p>
              <div style={{ position: 'relative', border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                <img
                  src={getFormPreviewUrl(job.id)}
                  alt="Form Preview Screenshot"
                  style={{ width: '100%', height: 'auto', display: 'block', borderRadius: 'var(--radius)' }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              </div>
            </div>
          )}

          {activeTab === 'contact' && (
            <div className="card flex flex-col gap-4">
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Discovered Contacts & Evidence
              </h3>
              {(job.contacts ?? []).length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '24px 0', textAlign: 'center' }}>
                  No contact details discovered for this target listing.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  {job.contacts.map((c) => {
                    const isExpanded = !!expandedEvidence[c.id];
                    const emailConf = c.email_confidence || 'unverified';
                    const isDraftingThis = draftContactId === c.id;

                    return (
                      <div key={c.id} style={{
                        padding: 16,
                        borderRadius: 'var(--radius)',
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 12
                      }}>
                        {/* Contact Header */}
                        <div className="flex justify-between items-start">
                          <div>
                            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>{c.name}</div>
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                              {c.title} {c.company ? `@ ${c.company}` : ''}
                            </div>
                          </div>
                          <div style={{ display: 'flex', gap: 6 }}>
                            {c.linkedin_url && (
                              <a
                                href={c.linkedin_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn btn-outline btn-xs"
                                style={{ fontSize: '10px', padding: '3px 8px', borderRadius: '4px' }}
                              >
                                LinkedIn ↗
                              </a>
                            )}
                          </div>
                        </div>

                        {/* Email row */}
                        {c.email && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                            <span style={{ color: 'var(--text-muted)' }}>Email:</span>
                            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{c.email}</span>
                            <span className={`badge ${emailConf === 'verified' ? 'badge-green' :
                                emailConf === 'inferred' ? 'badge-amber' : 'badge-muted'
                              }`} style={{ fontSize: '9px', padding: '1px 6px', textTransform: 'uppercase' }}>
                              {emailConf}
                            </span>
                          </div>
                        )}

                        {/* ── Outreach Draft Compose ─────────────────────────────── */}
                        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            Draft Outreach Message
                          </div>

                          {/* Channel + Tone Selectors */}
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {/* Channel toggle */}
                            <div style={{ display: 'flex', gap: 4 }}>
                              {(['linkedin', 'email'] as const).map(ch => (
                                <button
                                  key={ch}
                                  onClick={() => { setDraftChannel(ch); setDraftResult(null); }}
                                  style={{
                                    padding: '4px 10px', fontSize: '10px', fontWeight: 600,
                                    borderRadius: '9999px', cursor: 'pointer', border: '1px solid var(--border)',
                                    background: draftChannel === ch ? 'var(--text-primary)' : 'transparent',
                                    color: draftChannel === ch ? 'var(--bg-base)' : 'var(--text-secondary)',
                                    transition: 'all 0.15s'
                                  }}
                                >
                                  {ch === 'linkedin' ? '🔗 LinkedIn' : '✉️ Email'}
                                </button>
                              ))}
                            </div>

                            {/* Tone toggle */}
                            <div style={{ display: 'flex', gap: 4 }}>
                              {(['confident', 'warm'] as const).map(t => (
                                <button
                                  key={t}
                                  onClick={() => { setDraftTone(t); setDraftResult(null); }}
                                  style={{
                                    padding: '4px 10px', fontSize: '10px', fontWeight: 600,
                                    borderRadius: '9999px', cursor: 'pointer', border: '1px solid var(--border)',
                                    background: draftTone === t ? 'var(--amber)' : 'transparent',
                                    color: draftTone === t ? '#000' : 'var(--text-secondary)',
                                    transition: 'all 0.15s'
                                  }}
                                >
                                  {t === 'confident' ? '⚡ Direct/Confident' : '🤝 Warm/Curious'}
                                </button>
                              ))}
                            </div>

                            {/* Generate button */}
                            <button
                              className="btn btn-primary btn-sm"
                              style={{ borderRadius: '9999px', fontSize: '10px', padding: '4px 14px', marginLeft: 'auto' }}
                              disabled={draftLoading && isDraftingThis}
                              onClick={() => handleGenerateDraft(id, c.id)}
                            >
                              {draftLoading && isDraftingThis ? 'Generating…' : '✨ Generate Draft'}
                            </button>
                          </div>

                          {/* Draft Output */}
                          {isDraftingThis && draftResult && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                              <textarea
                                readOnly
                                value={draftResult.draft_text}
                                rows={draftChannel === 'linkedin' ? 4 : 8}
                                style={{
                                  width: '100%', resize: 'vertical', fontFamily: 'inherit',
                                  fontSize: '12px', lineHeight: 1.6,
                                  background: 'var(--bg-base)', color: 'var(--text-primary)',
                                  border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                                  padding: '10px 12px', outline: 'none'
                                }}
                              />
                              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                                <button
                                  className="btn btn-outline btn-sm"
                                  style={{ borderRadius: '9999px', fontSize: '10px', padding: '4px 12px' }}
                                  onClick={() => copyToClipboard(draftResult.draft_text)}
                                >
                                  📋 Copy Draft
                                </button>
                                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '11px', color: 'var(--text-secondary)', cursor: 'pointer', userSelect: 'none' }}>
                                  <input
                                    type="checkbox"
                                    checked={!!draftSentMap[draftResult.draft_id]}
                                    onChange={(e) => handleMarkSent(draftResult.draft_id, e.target.checked)}
                                    style={{ accentColor: 'var(--green)', width: 14, height: 14 }}
                                  />
                                  Mark as Sent
                                </label>
                                {draftSentMap[draftResult.draft_id] && (
                                  <span style={{ fontSize: '10px', color: 'var(--green)', fontWeight: 600 }}>✓ Sent</span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Evidence Accordion Panel */}
                        {c.evidence && c.evidence.length > 0 && (
                          <div style={{
                            borderTop: '1px solid var(--border)',
                            paddingTop: 10,
                            marginTop: 2
                          }}>
                            <button
                              onClick={() => toggleEvidence(c.id)}
                              style={{
                                background: 'none', border: 'none',
                                color: 'var(--text-secondary)', fontSize: '11px', fontWeight: 600,
                                cursor: 'pointer', display: 'flex', alignItems: 'center',
                                gap: 4, padding: 0, outline: 'none'
                              }}
                            >
                              <span>{isExpanded ? '▼' : '▶'}</span>
                              <span>Evidence Trail ({c.evidence.length})</span>
                            </button>

                            {isExpanded && (
                              <div style={{
                                display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10,
                                background: 'var(--bg-base)', padding: 12,
                                borderRadius: '4px', border: '1px solid var(--border)'
                              }}>
                                {c.evidence.map((ev: any, idx: number) => (
                                  <div key={idx} style={{ fontSize: '11px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                                    <div style={{ fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', fontSize: '9px', letterSpacing: '0.02em' }}>
                                      Verification Field: {ev.field || 'General Info'}
                                    </div>
                                    <blockquote style={{
                                      margin: 0, paddingLeft: 8,
                                      borderLeft: '2px solid var(--text-muted)',
                                      color: 'var(--text-secondary)', fontStyle: 'italic', lineHeight: 1.4
                                    }}>
                                      "{ev.snippet}"
                                    </blockquote>
                                    {ev.source_url && (
                                      <a href={ev.source_url} target="_blank" rel="noopener noreferrer"
                                        style={{ color: 'var(--text-muted)', textDecoration: 'underline', fontSize: '9px', wordBreak: 'break-all', marginTop: 1 }}
                                      >
                                        Source: {ev.source_url}
                                      </a>
                                    )}
                                    {idx < c.evidence!.length - 1 && <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '8px 0' }} />}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {activeTab === 'match' && (
            <div className="card flex flex-col gap-4">
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Match breakdown & rationale
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: 12, borderRadius: 'var(--radius)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Stage 1 Embedding Match</div>
                  <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, color: 'var(--text-primary)' }}>
                    {scoreDetails?.embedding_score != null ? `${(scoreDetails.embedding_score * 100).toFixed(1)}%` : '—'}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: 12, borderRadius: 'var(--radius)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Stage 2 LLM Reranker</div>
                  <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, color: 'var(--text-primary)' }}>
                    {scoreDetails?.llm_rerank_score != null ? `${(scoreDetails.llm_rerank_score * 100).toFixed(1)}%` : '—'}
                  </div>
                </div>
              </div>
              <div style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '16px',
                fontSize: '12px',
                lineHeight: 1.6,
                color: 'var(--text-secondary)',
                whiteSpace: 'pre-wrap',
              }}>
                {scoreDetails?.rationale || 'Scoring logic metadata description not available.'}
              </div>
            </div>
          )}

          {activeTab === 'log' && (
            <div className="card flex flex-col gap-3">
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Application History Timeline Log
              </h3>
              {(job.applications ?? []).length === 0 ? (
                <p style={{ fontSize: 12, color: 'var(--text-muted)', padding: '16px 0', textAlign: 'center' }}>
                  No audit history timeline events recorded.
                </p>
              ) : (
                <div className="table-wrap" style={{ marginTop: 4 }}>
                  <table style={{ fontSize: 12 }}>
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
                            <span className={`badge ${a.status === 'applied' ? 'badge-green' : 'badge-status-neutral'}`} style={{ textTransform: 'uppercase', fontSize: '10px' }}>
                              {a.status}
                            </span>
                          </td>
                          <td><span className="font-mono text-xs">{a.method}</span></td>
                          <td>{a.applied_at ? new Date(a.applied_at).toLocaleString() : '—'}</td>
                          <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={a.result ? (typeof a.result === 'object' ? JSON.stringify(a.result, null, 2) : String(a.result)) : ''}>
                            {a.result ? (
                              typeof a.result === 'object' ? (
                                (a.result as any).message || (a.result as any).error || JSON.stringify(a.result)
                              ) : String(a.result)
                            ) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

        </div>

        {/* RIGHT COLUMN: Sidebar controls, actions, metadata */}
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
                <>
                  {job.tier === 'A' ? (
                    <button
                      className="btn btn-primary btn-sm justify-center"
                      onClick={handleApply}
                      disabled={acting}
                      style={{ gap: 6, width: '100%', borderRadius: '9999px' }}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 12, height: 12 }}>
                        <polygon points="3 11 22 2 13 21 11 13 3 11" />
                      </svg>
                      <span>Auto Apply</span>
                    </button>
                  ) : job.tier === 'B' ? (
                    <button
                      className="btn btn-primary btn-sm justify-center"
                      onClick={handleApplyTierB}
                      disabled={acting}
                      style={{ gap: 6, width: '100%', borderRadius: '9999px' }}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 12, height: 12 }}>
                        <polygon points="3 11 22 2 13 21 11 13 3 11" />
                      </svg>
                      <span>Apply</span>
                    </button>
                  ) : (
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
                </>
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

        </aside>

      </div>
    </>
  );
}
