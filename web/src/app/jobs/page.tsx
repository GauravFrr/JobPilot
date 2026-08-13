'use client';
import useSWR from 'swr';
import { useState } from 'react';
import Link from 'next/link';
import { getJobs, type Job, type JobStatus, applyApplication, passApplication } from '@/lib/api';
import toast from 'react-hot-toast';
import { mutate } from 'swr';

const COLUMNS: { status: JobStatus; label: string; color: string }[] = [
  { status: 'matched',       label: 'Matched',       color: 'var(--accent)' },
  { status: 'tailoring',     label: 'Tailoring',     color: 'var(--blue)' },
  { status: 'ready_to_apply', label: 'Ready',        color: 'var(--amber)' },
  { status: 'applying',      label: 'Applying',      color: 'var(--amber)' },
  { status: 'applied',       label: 'Applied',       color: 'var(--green)' },
];

function scoreColor(score: number | null) {
  if (score == null) return 'var(--text-muted)';
  if (score >= 80) return 'var(--green)';
  if (score >= 60) return 'var(--amber)';
  return 'var(--red)';
}

function jobFetcher([, status]: [string, string]) {
  return getJobs({ status, per_page: 50 });
}

function KanbanColumn({ status, label, color }: { status: JobStatus; label: string; color: string }) {
  const { data, isLoading } = useSWR([`/jobs`, status], jobFetcher, { refreshInterval: 20000 });
  const jobs = data?.items ?? [];

  return (
    <div className="kanban-col">
      <div className="kanban-col-header">
        <span className="kanban-col-title" style={{ color }}>{label}</span>
        <span className="kanban-count">{isLoading ? '…' : jobs.length}</span>
      </div>
      {isLoading && (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto', width: 20, height: 20, borderWidth: 2 }} />
        </div>
      )}
      {jobs.map((job) => (
        <JobKanbanCard key={job.id} job={job} columnStatus={status} />
      ))}
      {!isLoading && jobs.length === 0 && (
        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
          Empty
        </div>
      )}
    </div>
  );
}

function JobKanbanCard({ job, columnStatus }: { job: Job; columnStatus: JobStatus }) {
  const [acting, setActing] = useState(false);
  const latestApp = job.applications?.[0];

  async function handleApply(e: React.MouseEvent) {
    e.preventDefault();
    if (!latestApp) return;
    setActing(true);
    try {
      await applyApplication(latestApp.id);
      toast.success('Applying...');
      mutate([`/jobs`, columnStatus]);
      mutate([`/jobs`, 'applying']);
    } catch (err: any) {
      toast.error(err.message || 'Apply failed');
    } finally {
      setActing(false);
    }
  }

  async function handlePass(e: React.MouseEvent) {
    e.preventDefault();
    if (!latestApp) return;
    setActing(true);
    try {
      await passApplication(latestApp.id);
      toast.success('Passed');
      mutate([`/jobs`, columnStatus]);
    } catch (err: any) {
      toast.error(err.message || 'Pass failed');
    } finally {
      setActing(false);
    }
  }

  return (
    <Link href={`/jobs/${job.id}`}>
      <div className="job-card">
        <div className="job-card-title truncate">{job.title}</div>
        <div className="job-card-company truncate">{job.company}</div>
        <div className="job-card-meta">
          <span
            className="badge"
            style={{
              background: 'var(--bg-surface)',
              color: scoreColor(job.match_score),
              fontFamily: 'var(--font-mono)',
            }}
          >
            {job.match_score != null ? `${job.match_score.toFixed(0)}%` : '—'}
          </span>
          <span className="badge badge-muted">{job.source}</span>
        </div>
        
        <div className="flex justify-between items-center" style={{ marginTop: 4 }}>
          {job.tier && (
            <span className={`badge ${
              job.tier === 'A' ? 'badge-green' :
              job.tier === 'B' ? 'badge-blue' :
              job.tier === 'C' ? 'badge-amber' : 'badge-muted'
            }`} style={{ alignSelf: 'flex-start' }}>
              Tier {job.tier}
            </span>
          )}
          {job.is_test && <span className="badge badge-red">TEST</span>}
        </div>

        {columnStatus === 'ready_to_apply' && latestApp && (
          <div className="job-card-actions" style={{ marginTop: 8 }}>
            <button
              className="btn btn-primary btn-xs"
              style={{ flex: 1 }}
              onClick={handleApply}
              disabled={acting}
            >
              Apply
            </button>
            <button
              className="btn btn-outline btn-xs"
              style={{ flex: 1 }}
              onClick={handlePass}
              disabled={acting}
            >
              Pass
            </button>
          </div>
        )}
      </div>
    </Link>
  );
}

// ─── Table View ──────────────────────────────────────────────────────────────

function TableView({ source, status }: { source: string; status: string }) {
  const params: Record<string, string> = { per_page: '100' };
  if (source) params.source = source;
  if (status) params.status = status;

  const { data, isLoading } = useSWR(
    ['/jobs/table', source, status],
    () => getJobs(params),
    { refreshInterval: 20000 }
  );

  const jobs = data?.items ?? [];

  if (isLoading) return <div className="loading-center"><div className="spinner" /></div>;

  if (!jobs.length) {
    return (
      <div className="empty">
        <div className="empty-icon">🗂️</div>
        <div className="empty-title">No applications found</div>
        <div className="empty-sub">Adjust the filters or wait for new jobs to come in</div>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Role</th>
            <th>Company</th>
            <th>Source</th>
            <th>Tier</th>
            <th>Score</th>
            <th>Status</th>
            <th>Applied</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <Link key={job.id} href={`/jobs/${job.id}`} legacyBehavior>
              <tr>
                <td style={{ color: 'var(--text-primary)', fontWeight: 600, maxWidth: 220 }} className="truncate">
                  {job.title}
                </td>
                <td className="truncate" style={{ maxWidth: 160 }}>{job.company}</td>
                <td><span className="badge badge-muted">{job.source}</span></td>
                <td>
                  {job.tier ? (
                    <span className={`badge ${
                      job.tier === 'A' ? 'badge-green' :
                      job.tier === 'B' ? 'badge-blue' :
                      job.tier === 'C' ? 'badge-amber' : 'badge-muted'
                    }`}>T{job.tier}</span>
                  ) : '—'}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: scoreColor(job.match_score) }}>
                  {job.match_score != null ? `${job.match_score.toFixed(0)}%` : '—'}
                </td>
                <td>
                  <StatusBadge status={job.status} />
                </td>
                <td style={{ fontSize: 12 }}>
                  {job.applied_at ? new Date(job.applied_at).toLocaleDateString() : '—'}
                </td>
              </tr>
            </Link>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ status }: { status: JobStatus }) {
  const map: Record<string, string> = {
    matched: 'badge-purple',
    tailoring: 'badge-blue',
    ready_to_apply: 'badge-amber',
    applying: 'badge-amber',
    applied: 'badge-green',
    discarded: 'badge-red',
    discovered: 'badge-muted',
  };
  return <span className={`badge ${map[status] ?? 'badge-muted'}`}>{status.replace(/_/g, ' ')}</span>;
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function JobsPage() {
  const [view, setView] = useState<'board' | 'table'>('board');
  const [filterSource, setFilterSource] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  return (
    <>
      <div className="page-header flex justify-between items-center">
        <div>
          <h1 className="page-title">Applications Board</h1>
          <p className="page-subtitle">All jobs in your pipeline</p>
        </div>
        <div className="tabs">
          <button className={`tab${view === 'board' ? ' active' : ''}`} onClick={() => setView('board')}>
            Board
          </button>
          <button className={`tab${view === 'table' ? ' active' : ''}`} onClick={() => setView('table')}>
            Table
          </button>
        </div>
      </div>

      {view === 'table' && (
        <div className="filters-bar">
          <select
            className="input"
            style={{ width: 'auto' }}
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {COLUMNS.map((c) => (
              <option key={c.status} value={c.status}>{c.label}</option>
            ))}
          </select>
          <select
            className="input"
            style={{ width: 'auto' }}
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value)}
          >
            <option value="">All sources</option>
            <option value="remoteok">RemoteOK</option>
            <option value="wwr">We Work Remotely</option>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
            <option value="linkedin">LinkedIn</option>
          </select>
        </div>
      )}

      {view === 'board' ? (
        <div className="kanban-wrapper">
          <div className="kanban-board">
            {COLUMNS.map((col) => (
              <KanbanColumn key={col.status} {...col} />
            ))}
          </div>
        </div>
      ) : (
        <TableView source={filterSource} status={filterStatus} />
      )}
    </>
  );
}
