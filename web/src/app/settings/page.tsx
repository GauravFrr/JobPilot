'use client';
import useSWR from 'swr';
import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import {
  getResumeProfile,
  updateResumeProfile,
  recomputeResumeEmbedding,
  getTargetCompanies,
  updateTargetCompanies,
  getThresholds,
  updateThresholds,
  getPlatformToggles,
  updatePlatformToggles,
  getDefaultAnswers,
  updateDefaultAnswers,
  generateTelegramPairingToken,
  type TargetCompany
} from '@/lib/api';

export default function SettingsPage() {
  // ─── SWR Fetches ───────────────────────────────────────────────────────────
  const { data: profile, mutate: mutateProfile, isLoading: loadingProfile } = useSWR('/settings/resume-profile', getResumeProfile);
  const { data: targetCompanies, mutate: mutateCompanies, isLoading: loadingCompanies } = useSWR('/settings/target-companies', getTargetCompanies);
  const { data: thresholds, mutate: mutateThresholds, isLoading: loadingThresholds } = useSWR('/settings/thresholds', getThresholds);
  const { data: toggles, mutate: mutateToggles, isLoading: loadingToggles } = useSWR('/settings/platform-toggles', getPlatformToggles);
  const { data: defaultAnswers, mutate: mutateAnswers, isLoading: loadingAnswers } = useSWR('/settings/default-answers', getDefaultAnswers);

  // ─── Local Edit States ─────────────────────────────────────────────────────
  const [profileText, setProfileText] = useState('');
  const [profileUnsaved, setProfileUnsaved] = useState(false);
  const [companiesList, setCompaniesList] = useState<TargetCompany[]>([]);
  const [minScore, setMinScore] = useState<number>(70);
  const [caps, setCaps] = useState<Record<string, number>>({});
  const [localToggles, setLocalToggles] = useState<Record<string, boolean>>({});
  const [answersText, setAnswersText] = useState('');
  const [pairingToken, setPairingToken] = useState<string | null>(null);

  // Sync SWR data to edit states
  useEffect(() => {
    if (profile?.content_json) {
      setProfileText(JSON.stringify(profile.content_json, null, 2));
      setProfileUnsaved(false);
    }
  }, [profile]);

  useEffect(() => {
    if (targetCompanies) setCompaniesList(targetCompanies);
  }, [targetCompanies]);

  useEffect(() => {
    if (thresholds) {
      setMinScore(thresholds.min_match_score);
      setCaps(thresholds.daily_caps_by_platform || {});
    }
  }, [thresholds]);

  useEffect(() => {
    if (toggles) setLocalToggles(toggles);
  }, [toggles]);

  useEffect(() => {
    if (defaultAnswers) setAnswersText(JSON.stringify(defaultAnswers, null, 2));
  }, [defaultAnswers]);

  // ─── Save Handlers ─────────────────────────────────────────────────────────
  const [savingSection, setSavingSection] = useState<string | null>(null);

  async function saveProfile() {
    setSavingSection('profile');
    try {
      const parsed = JSON.parse(profileText);
      await updateResumeProfile(parsed);
      setProfileUnsaved(false);
      toast.success('Resume profile updated. Embeddings are now stale.');
      mutateProfile();
    } catch (e: any) {
      toast.error(e.message || 'Invalid JSON format');
    } finally {
      setSavingSection(null);
    }
  }

  async function handleRecompute() {
    setSavingSection('recompute');
    try {
      await recomputeResumeEmbedding();
      toast.success('Embeddings recomputed successfully!');
      mutateProfile();
    } catch (e: any) {
      toast.error(e.message || 'Failed to recompute embeddings');
    } finally {
      setSavingSection(null);
    }
  }

  async function saveCompanies() {
    setSavingSection('companies');
    try {
      await updateTargetCompanies(companiesList);
      toast.success('Target companies saved');
      mutateCompanies();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSavingSection(null);
    }
  }

  async function saveThresholds() {
    setSavingSection('thresholds');
    try {
      await updateThresholds({ min_match_score: minScore, daily_caps_by_platform: caps });
      toast.success('Thresholds & Caps saved');
      mutateThresholds();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSavingSection(null);
    }
  }

  async function saveToggles() {
    setSavingSection('toggles');
    try {
      await updatePlatformToggles(localToggles);
      toast.success('Platform toggles saved');
      mutateToggles();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSavingSection(null);
    }
  }

  async function saveAnswers() {
    setSavingSection('answers');
    try {
      const parsed = JSON.parse(answersText);
      await updateDefaultAnswers(parsed);
      toast.success('Default screening answers saved');
      mutateAnswers();
    } catch (e: any) {
      toast.error(e.message || 'Invalid JSON format');
    } finally {
      setSavingSection(null);
    }
  }

  async function getPairToken() {
    try {
      const res = await generateTelegramPairingToken();
      setPairingToken(res.token);
      toast.success('Pairing token generated');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  const isLoading = loadingProfile || loadingCompanies || loadingThresholds || loadingToggles || loadingAnswers;

  if (isLoading) return <div className="loading-center"><div className="spinner" /></div>;

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Configure granular thresholds, resume profile matching, and automation preferences</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 24 }}>
        {/* Anchored Left Nav */}
        <aside style={{ position: 'sticky', top: 24, height: 'fit-content', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <a href="#resume-profile" className="nav-link" style={{ border: '1px solid var(--border)' }}>📄 Resume Profile</a>
          <a href="#target-companies" className="nav-link" style={{ border: '1px solid var(--border)' }}>🏢 Target Companies</a>
          <a href="#thresholds" className="nav-link" style={{ border: '1px solid var(--border)' }}>🎯 Thresholds & Caps</a>
          <a href="#platform-toggles" className="nav-link" style={{ border: '1px solid var(--border)' }}>📡 Platform Toggles</a>
          <a href="#default-answers" className="nav-link" style={{ border: '1px solid var(--border)' }}>📋 Screening Answers</a>
          <a href="#telegram" className="nav-link" style={{ border: '1px solid var(--border)' }}>💬 Telegram Bot</a>
        </aside>

        {/* Scrollable Single Page Content */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Section 1: Resume Profile */}
          <section id="resume-profile" className="card flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>📄 Resume Profile</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                  Active version: {profile?.version || '—'} · Last updated: {profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : '—'}
                </p>
              </div>
              <div className="flex gap-2">
                <button className="btn btn-outline btn-xs" onClick={handleRecompute} disabled={savingSection === 'recompute'}>
                  {savingSection === 'recompute' ? 'Recomputing...' : '🔄 Recompute Embeddings'}
                </button>
                <button className="btn btn-primary btn-xs" onClick={saveProfile} disabled={savingSection === 'profile'}>
                  {savingSection === 'profile' ? 'Saving...' : '💾 Save Profile'}
                </button>
              </div>
            </div>

            <textarea
              className="input font-mono"
              style={{ height: '300px', fontSize: '11px', lineHeight: '1.4' }}
              value={profileText}
              onChange={(e) => {
                setProfileText(e.target.value);
                setProfileUnsaved(true);
              }}
              placeholder="{}"
            />
            {profileUnsaved && (
              <div style={{ fontSize: 11, color: 'var(--amber)', fontWeight: 600 }}>
                ⚠ You have unsaved profile changes. Remember to recompute embeddings after saving!
              </div>
            )}
            {profile?.has_embedding === false && (
              <div style={{ fontSize: 11, color: 'var(--red)', fontWeight: 600 }}>
                ⚠ Embeddings are stale/missing. Tap 'Recompute Embeddings' to update the matcher cache.
              </div>
            )}
          </section>

          {/* Section 2: Target Companies */}
          <section id="target-companies" className="card flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>🏢 Target Companies</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Manage mapped ATS systems and target career URLs</p>
              </div>
              <button className="btn btn-primary btn-xs" onClick={saveCompanies} disabled={savingSection === 'companies'}>
                {savingSection === 'companies' ? 'Saving...' : '💾 Save Companies'}
              </button>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Company Name</th>
                    <th>Domain</th>
                    <th>Careers URL</th>
                    <th>ATS Type</th>
                    <th style={{ width: 60 }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {companiesList.map((c, idx) => (
                    <tr key={idx}>
                      <td>
                        <input
                          className="input btn-xs"
                          value={c.name}
                          onChange={(e) => {
                            const next = [...companiesList];
                            next[idx].name = e.target.value;
                            setCompaniesList(next);
                          }}
                        />
                      </td>
                      <td>
                        <input
                          className="input btn-xs"
                          value={c.domain || ''}
                          onChange={(e) => {
                            const next = [...companiesList];
                            next[idx].domain = e.target.value;
                            setCompaniesList(next);
                          }}
                        />
                      </td>
                      <td>
                        <input
                          className="input btn-xs"
                          value={c.careers_url || ''}
                          onChange={(e) => {
                            const next = [...companiesList];
                            next[idx].careers_url = e.target.value;
                            setCompaniesList(next);
                          }}
                        />
                      </td>
                      <td>
                        <select
                          className="input btn-xs"
                          value={c.detected_ats || 'generic'}
                          onChange={(e) => {
                            const next = [...companiesList];
                            next[idx].detected_ats = e.target.value;
                            setCompaniesList(next);
                          }}
                        >
                          <option value="greenhouse">Greenhouse</option>
                          <option value="lever">Lever</option>
                          <option value="generic">Generic/Other</option>
                        </select>
                      </td>
                      <td>
                        <button
                          className="btn btn-danger btn-xs"
                          onClick={() => setCompaniesList(companiesList.filter((_, i) => i !== idx))}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <button
              className="btn btn-outline btn-xs"
              style={{ alignSelf: 'flex-start' }}
              onClick={() => setCompaniesList([...companiesList, { name: 'New Company', domain: '', careers_url: '', detected_ats: 'generic' }])}
            >
              ➕ Add Row
            </button>
          </section>

          {/* Section 3: Thresholds & Caps */}
          <section id="thresholds" className="card flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>🎯 Thresholds & Caps</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Configure match parameters and system safeguards</p>
              </div>
              <button className="btn btn-primary btn-xs" onClick={saveThresholds} disabled={savingSection === 'thresholds'}>
                {savingSection === 'thresholds' ? 'Saving...' : '💾 Save Settings'}
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="detail-field">
                <label className="detail-label" htmlFor="min_match_score">Minimum Match Score (%)</label>
                <input
                  id="min_match_score"
                  type="number"
                  min={0}
                  max={100}
                  className="input"
                  value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                />
              </div>

              <div className="detail-field">
                <label className="detail-label">Daily Caps (LinkedIn / Greenhouse)</label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                  {['linkedin', 'greenhouse', 'lever', 'remoteok'].map((platform) => (
                    <div key={platform} className="flex items-center justify-between">
                      <span className="font-mono text-xs">{platform}</span>
                      <input
                        type="number"
                        className="input btn-xs"
                        style={{ width: 80 }}
                        value={caps[platform] ?? 10}
                        onChange={(e) => setCaps({ ...caps, [platform]: Number(e.target.value) })}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* Section 4: Platform Toggles */}
          <section id="platform-toggles" className="card flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>📡 Platform Toggles</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Enable/disable crawling sources instantly</p>
              </div>
              <button className="btn btn-primary btn-xs" onClick={saveToggles} disabled={savingSection === 'toggles'}>
                {savingSection === 'toggles' ? 'Saving...' : '💾 Save Toggles'}
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {Object.keys(localToggles).length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No toggles configured.</div>
              ) : (
                Object.entries(localToggles).map(([platform, enabled]) => (
                  <div key={platform} className="flex items-center gap-2">
                    <input
                      id={`toggle-${platform}`}
                      type="checkbox"
                      checked={enabled}
                      onChange={(e) => setLocalToggles({ ...localToggles, [platform]: e.target.checked })}
                      style={{ width: 14, height: 14, cursor: 'pointer' }}
                    />
                    <label htmlFor={`toggle-${platform}`} style={{ fontSize: 12, cursor: 'pointer' }} className="font-mono">
                      {platform}
                    </label>
                  </div>
                ))
              )}
            </div>
          </section>

          {/* Section 5: Default Answers */}
          <section id="default-answers" className="card flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>📋 Screening Answers</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Structured JSON feeding the form-filling engine</p>
              </div>
              <button className="btn btn-primary btn-xs" onClick={saveAnswers} disabled={savingSection === 'answers'}>
                {savingSection === 'answers' ? 'Saving...' : '💾 Save Answers'}
              </button>
            </div>

            <textarea
              className="input font-mono"
              style={{ height: '160px', fontSize: '11px', lineHeight: '1.4' }}
              value={answersText}
              onChange={(e) => setAnswersText(e.target.value)}
              placeholder="{}"
            />
          </section>

          {/* Section 6: Telegram Pairing */}
          <section id="telegram" className="card flex flex-col gap-3">
            <h3 style={{ fontSize: 14, fontWeight: 700 }}>💬 Telegram Bot Connection</h3>
            <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Pair the automation center with your private chat ID</p>

            <div className="flex items-center gap-3" style={{ marginTop: 4 }}>
              <button className="btn btn-outline btn-xs" onClick={getPairToken}>
                🔑 Generate Pairing Token
              </button>
              {pairingToken && (
                <div style={{
                  background: 'var(--bg-surface)',
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border)',
                  fontSize: '12px',
                  fontWeight: 700,
                  fontFamily: 'var(--font-mono)'
                }}>
                  {pairingToken}
                </div>
              )}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              Generate token, then send <code className="font-mono" style={{ background: 'var(--bg-surface)', padding: '1px 4px' }}>/start [token]</code> to the Telegram bot to pair.
            </div>
          </section>

        </div>
      </div>
    </>
  );
}
