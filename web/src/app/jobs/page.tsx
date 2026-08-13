'use client';
import useSWR, { mutate } from 'swr';
import { useState } from 'react';
import Link from 'next/link';
import { getJobs, type Job, type JobStatus, passApplication, markApplied } from '@/lib/api';
import toast from 'react-hot-toast';

const STATUSES: { status: JobStatus; label: string; color: string }[] = [
  { status: 'matched',        label: 'Matched',        color: 'var(--text-secondary)' },
  { status: 'tailoring',      label: 'Tailoring',      color: 'var(--blue)' },
  { status: 'ready_to_apply',  label: 'Ready to Apply', color: 'var(--amber)' },
  { status: 'applying',       label: 'Applying',       color: 'var(--amber)' },
  { status: 'applied',        label: 'Applied',        color: 'var(--green)' },
];

function scoreColor(score: number | null) {
  if (score == null) return 'var(--text-muted)';
  if (score >= 80) return 'var(--green)';
  if (score >= 60) return 'var(--amber)';
  return 'var(--red)';
}

export default function JobsPage() {
  const [activeStatus, setActiveStatus] = useState<JobStatus>('matched');
  const [actingId, setActingId] = useState<string | null>(null);

  // Fetch all statuses in parallel to get live counts in pills
  const { data: matchedData, mutate: mutateMatched } = useSWR(['/jobs', 'matched'], () => getJobs({ status: 'matched', per_page: 100 }), { refreshInterval: 15000 });
  const { data: tailoringData, mutate: mutateTailoring } = useSWR(['/jobs', 'tailoring'], () => getJobs({ status: 'tailoring', per_page: 100 }), { refreshInterval: 15000 });
  const { data: readyData, mutate: mutateReady } = useSWR(['/jobs', 'ready_to_apply'], () => getJobs({ status: 'ready_to_apply', per_page: 100 }), { refreshInterval: 15000 });
  const { data: applyingData, mutate: mutateApplying } = useSWR(['/jobs', 'applying'], () => getJobs({ status: 'applying', per_page: 100 }), { refreshInterval: 15000 });
  const { data: appliedData, mutate: mutateApplied } = useSWR(['/jobs', 'applied'], () => getJobs({ status: 'applied', per_page: 100 }), { refreshInterval: 15000 });

  const getJobsList = () => {
    switch (activeStatus) {
      case 'matched': return matchedData?.items ?? [];
      case 'tailoring': return tailoringData?.items ?? [];
      case 'ready_to_apply': return readyData?.items ?? [];
      case 'applying': return applyingData?.items ?? [];
      case 'applied': return appliedData?.items ?? [];
      default: return [];
    }
  };

  const getCount = (status: JobStatus) => {
    switch (status) {
      case 'matched': return matchedData?.total ?? 0;
      case 'tailoring': return tailoringData?.total ?? 0;
      case 'ready_to_apply': return readyData?.total ?? 0;
      case 'applying': return applyingData?.total ?? 0;
      case 'applied': return appliedData?.total ?? 0;
      default: return 0;
    }
  };

  const forceMutateAll = () => {
    mutateMatched();
    mutateTailoring();
    mutateReady();
    mutateApplying();
    mutateApplied();
  };

  async function handlePass(e: React.MouseEvent, jobId: string, appId: string) {
    e.preventDefault();
    e.stopPropagation();
    setActingId(jobId);
    try {
      await passApplication(appId);
      toast.success('Job passed');
      forceMutateAll();
    } catch (err: any) {
      toast.error(err.message || 'Pass failed');
    } finally {
      setActingId(null);
    }
  }

  async function handleMarkApplied(e: React.MouseEvent, jobId: string, appId: string) {
    e.preventDefault();
    e.stopPropagation();
    setActingId(jobId);
    try {
      await markApplied(appId);
      toast.success('Marked as applied');
      forceMutateAll();
    } catch (err: any) {
      toast.error(err.message || 'Action failed');
    } finally {
      setActingId(null);
    }
  }

  const jobsList = getJobsList();

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">Applications Board</h1>
        <p className="page-subtitle">Manage your jobs pipeline in full-width list view</p>
      </div>

      {/* Row of Category Filter Pills */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 10,
        marginBottom: 20,
        paddingBottom: 14,
        borderBottom: '1px solid var(--border)'
      }}>
        {STATUSES.map(({ status, label, color }) => {
          const isActive = activeStatus === status;
          const count = getCount(status);
          return (
            <button
              key={status}
              onClick={() => setActiveStatus(status)}
              className="flex items-center gap-2"
              style={{
                background: isActive ? 'var(--text-primary)' : 'var(--bg-card)',
                color: isActive ? 'var(--bg-base)' : 'var(--text-primary)',
                border: '1px solid var(--border)',
                borderRadius: '9999px',
                padding: '6px 16px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.1s ease',
                outline: 'none'
              }}
            >
              <span style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                backgroundColor: isActive ? 'var(--bg-base)' : color
              }} />
              <span>{label}</span>
              <span style={{
                opacity: 0.6,
                fontSize: '10px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: isActive ? 'rgba(0,0,0,0.1)' : 'var(--bg-elevated)',
                padding: '1px 6px',
                borderRadius: '9999px',
                color: isActive ? 'var(--bg-base)' : 'var(--text-secondary)'
              }}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Main Full-Width Jobs List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {jobsList.length === 0 ? (
          <div className="card flex flex-col items-center justify-center" style={{ padding: '60px 20px', textAlign: 'center' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 32, height: 32, color: 'var(--text-muted)', marginBottom: 12 }}>
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>No jobs found</div>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
              There are no jobs in the "{STATUSES.find(s => s.status === activeStatus)?.label}" pipeline stage.
            </p>
          </div>
        ) : (
          jobsList.map((job) => {
            const latestApp = job.applications?.[0];
            return (
              <Link href={`/jobs/${job.id}`} key={job.id}>
                <div className="card" style={{
                  padding: '14px 20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 16,
                  cursor: 'pointer'
                }}>
                  {/* Left part: Title & metadata */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <h2 className="truncate" style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', margin: 0, maxWidth: '400px' }}>
                        {job.title}
                      </h2>
                      <span className="badge font-mono font-bold" style={{ background: 'var(--bg-surface)', color: scoreColor(job.match_score) }}>
                        {job.match_score != null ? `${job.match_score.toFixed(1)}%` : '—'}
                      </span>
                      {job.tier && (
                        <span className={`badge ${
                          job.tier === 'A' ? 'badge-green' :
                          job.tier === 'B' ? 'badge-blue' :
                          job.tier === 'C' ? 'badge-amber' : 'badge-muted'
                        }`}>
                          Tier {job.tier}
                        </span>
                      )}
                      {job.is_test && <span className="badge badge-red" style={{ fontSize: '9px', padding: '1px 5px' }}>TEST</span>}
                    </div>
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                      <span style={{ fontWeight: 600 }}>{job.company}</span>
                      <span>·</span>
                      <span>{job.source}</span>
                      {job.created_at && (
                        <>
                          <span>·</span>
                          <span style={{ color: 'var(--text-muted)' }}>Discovered {new Date(job.created_at).toLocaleDateString()}</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Right part: Actions */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
                    
                    {/* Action buttons based on activeStatus */}
                    {activeStatus === 'ready_to_apply' && latestApp && (
                      <>
                        <button
                          className="btn btn-primary btn-sm"
                          style={{ borderRadius: '9999px', fontSize: '11px', padding: '5px 12px' }}
                          disabled={actingId === job.id}
                          onClick={(e) => handleMarkApplied(e, job.id, latestApp.id)}
                        >
                          Mark Applied
                        </button>
                        <button
                          className="btn btn-outline btn-sm"
                          style={{ borderRadius: '9999px', fontSize: '11px', padding: '5px 12px' }}
                          disabled={actingId === job.id}
                          onClick={(e) => handlePass(e, job.id, latestApp.id)}
                        >
                          Pass
                        </button>
                      </>
                    )}

                    {activeStatus === 'matched' && latestApp && (
                      <button
                        className="btn btn-outline btn-sm"
                        style={{ borderRadius: '9999px', fontSize: '11px', padding: '5px 12px' }}
                        disabled={actingId === job.id}
                        onClick={(e) => handlePass(e, job.id, latestApp.id)}
                      >
                        Pass Role
                      </button>
                    )}

                    {/* View Original Listing external link */}
                    {job.url && (
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-outline btn-sm"
                        style={{ borderRadius: '9999px', fontSize: '11px', padding: '5px 10px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                      >
                        <span>Original</span>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 10, height: 10 }}>
                          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                          <polyline points="15 3 21 3 21 9" />
                          <line x1="10" y1="14" x2="21" y2="3" />
                        </svg>
                      </a>
                    )}
                  </div>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </>
  );
}
