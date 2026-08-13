'use client';
import useSWR from 'swr';
import { useState } from 'react';
import toast from 'react-hot-toast';
import { getSettings, updateSettings, type Settings } from '@/lib/api';

export default function SettingsPage() {
  const { data, isLoading, mutate } = useSWR<Settings>('/settings', getSettings);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Partial<Settings>>({});

  const current = { ...data, ...form };

  async function handleSave() {
    setSaving(true);
    try {
      await updateSettings(form);
      toast.success('Settings saved');
      mutate();
      setForm({});
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function patch(key: keyof Settings, value: unknown) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  if (isLoading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <>
      <div className="page-header flex justify-between items-center">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Automation & pipeline preferences</p>
        </div>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving || Object.keys(form).length === 0}>
          {saving ? 'Saving…' : '💾 Save Changes'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Matching */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>
            🎯 Matching Engine
          </h3>

          <div className="detail-field">
            <label className="detail-label" htmlFor="min_match_score">Min Match Score (%)</label>
            <input
              id="min_match_score"
              type="number"
              min={0}
              max={100}
              className="input"
              value={current.min_match_score ?? 70}
              onChange={(e) => patch('min_match_score', Number(e.target.value))}
            />
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              Jobs scoring below this threshold are discarded (default: 70)
            </div>
          </div>
        </div>

        {/* Automation */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>
            ⚡ Automation
          </h3>

          <div className="detail-field">
            <label className="detail-label" htmlFor="auto_apply_tier">Auto-apply Tier</label>
            <select
              id="auto_apply_tier"
              className="input"
              value={current.auto_apply_tier ?? 'A'}
              onChange={(e) => patch('auto_apply_tier', e.target.value)}
            >
              <option value="A">Tier A (fully automated)</option>
              <option value="B">Tier B (semi-automated)</option>
              <option value="C">Tier C (manual review)</option>
              <option value="none">None (manual only)</option>
            </select>
          </div>

          <div className="detail-field" style={{ marginTop: 16 }}>
            <label className="detail-label">Pause Automation</label>
            <div className="flex items-center gap-2" style={{ marginTop: 6 }}>
              <input
                id="pause_automation"
                type="checkbox"
                checked={current.pause_automation ?? false}
                onChange={(e) => patch('pause_automation', e.target.checked)}
                style={{ width: 16, height: 16, cursor: 'pointer', accentColor: 'var(--accent)' }}
              />
              <label htmlFor="pause_automation" style={{ fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Pause all automation (scraping, matching, applying)
              </label>
            </div>
          </div>
        </div>

        {/* Telegram */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>
            💬 Telegram Bot
          </h3>
          <div className="detail-field">
            <label className="detail-label">Chat ID</label>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-primary)', padding: '8px 0' }}>
              {current.chat_id ?? <span style={{ color: 'var(--text-muted)' }}>Not paired yet</span>}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Pair by sending <code style={{ background: 'var(--bg-elevated)', padding: '1px 5px', borderRadius: 4 }}>/start</code> to your bot
            </div>
          </div>
        </div>

        {/* Sources */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>
            📡 Preferred Sources
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {['remoteok', 'wwr', 'greenhouse', 'lever', 'linkedin'].map((src) => {
              const preferred = current.preferred_sources ?? [];
              const checked = preferred.includes(src);
              return (
                <div key={src} className="flex items-center gap-2">
                  <input
                    id={`src-${src}`}
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      const next = e.target.checked
                        ? [...preferred, src]
                        : preferred.filter((s) => s !== src);
                      patch('preferred_sources', next);
                    }}
                    style={{ width: 16, height: 16, cursor: 'pointer', accentColor: 'var(--accent)' }}
                  />
                  <label htmlFor={`src-${src}`} style={{ fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                    {src}
                  </label>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
