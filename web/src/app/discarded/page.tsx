'use client';
import useSWR from 'swr';
import { getJobs, type Job } from '@/lib/api';
import Link from 'next/link';

export default function DiscardedPage() {
  const { data, isLoading } = useSWR(
    '/jobs/discarded',
    () => getJobs({ status: 'discarded', per_page: 100 }),
    { refreshInterval: 60000 }
  );

  const jobs = data?.items ?? [];

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
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Role</th>
                <th>Company</th>
                <th>Source</th>
                <th>Score</th>
                <th>Tier</th>
                <th>Discovered</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job: Job) => (
                <Link key={job.id} href={`/jobs/${job.id}`} legacyBehavior>
                  <tr>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{job.title}</td>
                    <td>{job.company}</td>
                    <td><span className="badge badge-muted">{job.source}</span></td>
                    <td style={{
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 700,
                      color: job.match_score != null && job.match_score < 50 ? 'var(--red)' : 'var(--text-muted)',
                    }}>
                      {job.match_score != null ? `${job.match_score.toFixed(0)}%` : '—'}
                    </td>
                    <td>{job.tier ?? '—'}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {job.created_at ? new Date(job.created_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                </Link>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
