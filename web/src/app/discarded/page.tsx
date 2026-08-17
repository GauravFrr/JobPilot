'use client';
import { useState } from 'react';
import useSWR from 'swr';
import { getJobs, getJob, type Job } from '@/lib/api';
import Link from 'next/link';

export default function DiscardedPage() {
  const { data, isLoading } = useSWR(
    '/jobs/discarded',
    () => getJobs({ status: 'discarded', per_page: 100 }),
    { refreshInterval: 60000 }
  );

  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [jobDetails, setJobDetails] = useState<Record<string, any>>({});
  const [loadingDetailId, setLoadingDetailId] = useState<string | null>(null);

  const jobs = data?.items ?? [];

  const handleCardClick = async (jobId: string) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null);
      return;
    }
    setExpandedJobId(jobId);

    // Fetch full details if not already loaded/cached
    if (!jobDetails[jobId]) {
      setLoadingDetailId(jobId);
      try {
        const data = await getJob(jobId);
        setJobDetails(prev => ({ ...prev, [jobId]: data }));
      } catch (err) {
        console.error('Failed to load discarded job details:', err);
      } finally {
        setLoadingDetailId(null);
      }
    }
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Discarded Jobs</h1>
        <p className="page-subtitle">
          Jobs that were filtered out by the matching engine ({jobs.length} total)
        </p>
      </div>

      {isLoading ? (
        <div className="loading-center"><div className="spinner" /></div>
      ) : jobs.length === 0 ? (
        <div className="empty">
          <div className="empty-title">No discarded jobs</div>
          <div className="empty-sub">All jobs passing the threshold will be shown in the Applications Board</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {jobs.map((job: Job) => {
            const isExpanded = expandedJobId === job.id;
            return (
              <div
                key={job.id}
                className="card"
                style={{
                  padding: '16px 20px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  border: '1px solid var(--border)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12
                }}
                onClick={() => handleCardClick(job.id)}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0, flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <h3 className="truncate" style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                        {job.title}
                      </h3>
                      <span className="badge font-mono font-bold" style={{ background: 'var(--bg-surface)', color: 'var(--red)' }}>
                        {job.match_score != null ? `${job.match_score.toFixed(0)}%` : '—'}
                      </span>
                      <span className="badge badge-muted">{job.source}</span>
                      {job.tier && (
                        <span className={`badge ${
                          job.tier === 'A' ? 'badge-green' :
                          job.tier === 'B' ? 'badge-blue' :
                          job.tier === 'C' ? 'badge-amber' : 'badge-muted'
                        }`}>
                          Tier {job.tier}
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{job.company}</span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {job.created_at ? new Date(job.created_at).toLocaleDateString() : '—'}
                    </span>
                    <svg
                      style={{
                        width: 16,
                        height: 16,
                        color: 'var(--text-secondary)',
                        transform: isExpanded ? 'rotate(180deg)' : 'none',
                        transition: 'transform 0.2s ease'
                      }}
                      viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </div>
                </div>

                {isExpanded && (
                  <div
                    style={{
                      borderTop: '1px solid var(--border)',
                      paddingTop: 12,
                      marginTop: 4,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 12,
                      fontSize: 12,
                      lineHeight: 1.5
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {loadingDetailId === job.id ? (
                      <div className="flex justify-center py-4"><div className="spinner" style={{ width: 20, height: 20 }} /></div>
                    ) : jobDetails[job.id] ? (
                      <>
                        <div className="card" style={{ background: 'var(--bg-surface)', padding: 12, borderRadius: 'var(--radius)' }}>
                          <h4 style={{ fontWeight: 700, marginBottom: 6, fontSize: 12 }}>Gemini Match Rationale</h4>
                          <p style={{ color: 'var(--text-secondary)', whiteSpace: 'pre-line' }}>
                            {jobDetails[job.id].score?.rationale || 'No rationale details returned from database.'}
                          </p>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                          {job.url && (
                            <a
                              href={job.url}
                              target="_blank"
                              rel="noreferrer"
                              className="btn btn-outline btn-xs"
                              style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
                            >
                              Open Job Page ↗
                            </a>
                          )}
                          <Link href={`/jobs/${job.id}`} className="btn btn-primary btn-xs" style={{ marginLeft: 'auto' }}>
                            View Detail Page
                          </Link>
                        </div>
                      </>
                    ) : (
                      <div style={{ color: 'var(--red)', fontWeight: 600 }}>Failed to load job details.</div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
