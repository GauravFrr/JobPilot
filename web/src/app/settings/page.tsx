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
  const [resumeEditMode, setResumeEditMode] = useState<'form' | 'json'>('form');
  const [profileData, setProfileData] = useState<any>({
    name: '',
    target_roles: [],
    skills: {},
    experience: [],
    projects: []
  });

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
      const raw = profile.content_json;
      setProfileData({
        name: raw.name || '',
        target_roles: Array.isArray(raw.target_roles) ? raw.target_roles : [],
        skills: (raw.skills && typeof raw.skills === 'object') ? raw.skills : {},
        experience: Array.isArray(raw.experience) ? raw.experience : [],
        projects: Array.isArray(raw.projects) ? raw.projects : [],
        ...raw
      });
      setProfileUnsaved(false);
    }
  }, [profile]);

  const updateProfileField = (key: string, value: any) => {
    const updated = {
      ...profileData,
      [key]: value
    };
    setProfileData(updated);
    setProfileText(JSON.stringify(updated, null, 2));
    setProfileUnsaved(true);
  };

  const handleTabChange = (mode: 'form' | 'json') => {
    if (mode === 'form') {
      try {
        const parsed = JSON.parse(profileText);
        setProfileData({
          name: parsed.name || '',
          target_roles: Array.isArray(parsed.target_roles) ? parsed.target_roles : [],
          skills: (parsed.skills && typeof parsed.skills === 'object') ? parsed.skills : {},
          experience: Array.isArray(parsed.experience) ? parsed.experience : [],
          projects: Array.isArray(parsed.projects) ? parsed.projects : [],
          ...parsed
        });
      } catch (e) {
        toast.error('Cannot switch to form view: Invalid JSON syntax in editor.');
        return;
      }
    }
    setResumeEditMode(mode);
  };

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
          <a href="#resume-profile" className="nav-link" style={{ border: '1px solid var(--border)' }}>Resume Profile</a>
          <a href="#target-companies" className="nav-link" style={{ border: '1px solid var(--border)' }}>Target Companies</a>
          <a href="#thresholds" className="nav-link" style={{ border: '1px solid var(--border)' }}>Thresholds & Caps</a>
          <a href="#platform-toggles" className="nav-link" style={{ border: '1px solid var(--border)' }}>Platform Toggles</a>
          <a href="#default-answers" className="nav-link" style={{ border: '1px solid var(--border)' }}>Screening Answers</a>
          <a href="#telegram" className="nav-link" style={{ border: '1px solid var(--border)' }}>Telegram Bot</a>
        </aside>

        {/* Scrollable Single Page Content */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Section 1: Resume Profile */}
          <section id="resume-profile" className="card flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>Resume Profile</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                  Active version: {profile?.version || '—'} · Last updated: {profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : '—'}
                </p>
              </div>
              <div className="flex gap-2">
                <button className="btn btn-outline btn-xs" onClick={handleRecompute} disabled={savingSection === 'recompute'}>
                  {savingSection === 'recompute' ? 'Recomputing...' : 'Recompute Embeddings'}
                </button>
                <button className="btn btn-primary btn-xs" onClick={saveProfile} disabled={savingSection === 'profile'}>
                  {savingSection === 'profile' ? 'Saving...' : 'Save Profile'}
                </button>
              </div>
            </div>

            {/* View Mode Selector Tabs */}
            <div className="flex gap-2" style={{ borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
              <button
                type="button"
                className={`btn btn-xs ${resumeEditMode === 'form' ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => handleTabChange('form')}
              >
                Visual Editor
              </button>
              <button
                type="button"
                className={`btn btn-xs ${resumeEditMode === 'json' ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => handleTabChange('json')}
              >
                Raw JSON
              </button>
            </div>

            {resumeEditMode === 'json' ? (
              <textarea
                className="input font-mono"
                style={{ height: '350px', fontSize: '11px', lineHeight: '1.4' }}
                value={profileText}
                onChange={(e) => {
                  setProfileText(e.target.value);
                  setProfileUnsaved(true);
                }}
                placeholder="{}"
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', fontSize: '12px' }}>
                {/* Name & Target Roles */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="detail-field">
                    <label className="detail-label" style={{ fontWeight: '600', marginBottom: '4px', display: 'block' }}>Name</label>
                    <input
                      className="input"
                      value={profileData.name}
                      onChange={(e) => updateProfileField('name', e.target.value)}
                      placeholder="Your Name"
                    />
                  </div>
                  <div className="detail-field">
                    <label className="detail-label" style={{ fontWeight: '600', marginBottom: '4px', display: 'block' }}>Target Roles (comma-separated)</label>
                    <input
                      className="input"
                      value={profileData.target_roles.join(', ')}
                      onChange={(e) => {
                        const roles = e.target.value.split(',').map(r => r.trim()).filter(Boolean);
                        updateProfileField('target_roles', roles);
                      }}
                      placeholder="e.g. Software Engineer, Machine Learning Engineer"
                    />
                  </div>
                </div>

                {/* Skills Section */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
                  <h4 style={{ fontWeight: '700', fontSize: '12px' }}>Skills Categories</h4>
                  {Object.entries(profileData.skills || {}).map(([category, items], idx) => {
                    const itemsStr = Array.isArray(items) ? items.join(', ') : String(items);
                    return (
                      <div key={category} style={{ display: 'grid', gridTemplateColumns: '150px 1fr 40px', gap: '8px', alignItems: 'center' }}>
                        <input
                          className="input"
                          style={{ height: '28px', fontSize: '11px' }}
                          value={category}
                          onChange={(e) => {
                            const newCategory = e.target.value.trim();
                            if (!newCategory || newCategory === category) return;
                            const newSkills = { ...profileData.skills };
                            newSkills[newCategory] = newSkills[category];
                            delete newSkills[category];
                            updateProfileField('skills', newSkills);
                          }}
                          placeholder="Category Name"
                        />
                        <input
                          className="input"
                          style={{ height: '28px', fontSize: '11px' }}
                          value={itemsStr}
                          onChange={(e) => {
                            const newSkills = { ...profileData.skills };
                            newSkills[category] = e.target.value.split(',').map(s => s.trim()).filter(Boolean);
                            updateProfileField('skills', newSkills);
                          }}
                          placeholder="Python, Java, Go..."
                        />
                        <button
                          type="button"
                          className="btn btn-danger btn-xs"
                          style={{ height: '28px' }}
                          onClick={() => {
                            const newSkills = { ...profileData.skills };
                            delete newSkills[category];
                            updateProfileField('skills', newSkills);
                          }}
                        >
                          ✕
                        </button>
                      </div>
                    );
                  })}
                  <button
                    type="button"
                    className="btn btn-outline btn-xs"
                    style={{ alignSelf: 'flex-start', marginTop: '4px' }}
                    onClick={() => {
                      const newSkills = { ...profileData.skills };
                      newSkills[`New Category ${Object.keys(newSkills).length + 1}`] = [];
                      updateProfileField('skills', newSkills);
                    }}
                  >
                    + Add Category
                  </button>
                </div>

                {/* Experience Section */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
                  <h4 style={{ fontWeight: '700', fontSize: '12px' }}>Work Experience</h4>
                  {profileData.experience.map((exp: any, expIdx: number) => (
                    <div key={expIdx} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 40px', gap: '8px', alignItems: 'center' }}>
                        <input
                          className="input"
                          style={{ height: '28px', fontSize: '11px' }}
                          value={exp.role || ''}
                          onChange={(e) => {
                            const next = [...profileData.experience];
                            next[expIdx] = { ...next[expIdx], role: e.target.value };
                            updateProfileField('experience', next);
                          }}
                          placeholder="Role (e.g. Senior Developer)"
                        />
                        <input
                          className="input"
                          style={{ height: '28px', fontSize: '11px' }}
                          value={exp.company || ''}
                          onChange={(e) => {
                            const next = [...profileData.experience];
                            next[expIdx] = { ...next[expIdx], company: e.target.value };
                            updateProfileField('experience', next);
                          }}
                          placeholder="Company (e.g. Google)"
                        />
                        <button
                          type="button"
                          className="btn btn-danger btn-xs"
                          style={{ height: '28px' }}
                          onClick={() => {
                            const next = profileData.experience.filter((_: any, i: number) => i !== expIdx);
                            updateProfileField('experience', next);
                          }}
                        >
                          ✕
                        </button>
                      </div>

                      {/* Bullets */}
                      <div style={{ paddingLeft: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <span style={{ fontSize: '10px', fontWeight: '600', color: 'var(--text-secondary)' }}>Bullets (Tailored keywords)</span>
                        {(exp.bullets || []).map((b: string, bulletIdx: number) => (
                          <div key={bulletIdx} style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <input
                              className="input"
                              style={{ height: '26px', fontSize: '11px' }}
                              value={b}
                              onChange={(e) => {
                                const nextExps = [...profileData.experience];
                                const nextBullets = [...(nextExps[expIdx].bullets || [])];
                                nextBullets[bulletIdx] = e.target.value;
                                nextExps[expIdx] = { ...nextExps[expIdx], bullets: nextBullets };
                                updateProfileField('experience', nextExps);
                              }}
                              placeholder="Achievement bullet..."
                            />
                            <button
                              type="button"
                              className="btn btn-outline btn-xs"
                              style={{ height: '26px', padding: '0 6px' }}
                              onClick={() => {
                                const nextExps = [...profileData.experience];
                                const nextBullets = (nextExps[expIdx].bullets || []).filter((_: any, i: number) => i !== bulletIdx);
                                nextExps[expIdx] = { ...nextExps[expIdx], bullets: nextBullets };
                                updateProfileField('experience', nextExps);
                              }}
                            >
                              ✕
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          className="btn btn-outline btn-xs"
                          style={{ alignSelf: 'flex-start', height: '24px', fontSize: '10px' }}
                          onClick={() => {
                            const nextExps = [...profileData.experience];
                            const nextBullets = [...(nextExps[expIdx].bullets || []), ''];
                            nextExps[expIdx] = { ...nextExps[expIdx], bullets: nextBullets };
                            updateProfileField('experience', nextExps);
                          }}
                        >
                          + Add Bullet
                        </button>
                      </div>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="btn btn-outline btn-xs"
                    style={{ alignSelf: 'flex-start' }}
                    onClick={() => {
                      const next = [...profileData.experience, { role: '', company: '', bullets: [] }];
                      updateProfileField('experience', next);
                    }}
                  >
                    + Add Experience
                  </button>
                </div>

                {/* Projects Section */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
                  <h4 style={{ fontWeight: '700', fontSize: '12px' }}>Projects</h4>
                  {profileData.projects.map((proj: any, projIdx: number) => (
                    <div key={projIdx} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 40px', gap: '8px', alignItems: 'center' }}>
                        <input
                          className="input"
                          style={{ height: '28px', fontSize: '11px' }}
                          value={proj.name || ''}
                          onChange={(e) => {
                            const next = [...profileData.projects];
                            next[projIdx] = { ...next[projIdx], name: e.target.value };
                            updateProfileField('projects', next);
                          }}
                          placeholder="Project Name"
                        />
                        <button
                          type="button"
                          className="btn btn-danger btn-xs"
                          style={{ height: '28px' }}
                          onClick={() => {
                            const next = profileData.projects.filter((_: any, i: number) => i !== projIdx);
                            updateProfileField('projects', next);
                          }}
                        >
                          ✕
                        </button>
                      </div>

                      {/* Bullets */}
                      <div style={{ paddingLeft: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <span style={{ fontSize: '10px', fontWeight: '600', color: 'var(--text-secondary)' }}>Bullets (Project achievements)</span>
                        {(proj.bullets || []).map((b: string, bulletIdx: number) => (
                          <div key={bulletIdx} style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <input
                              className="input"
                              style={{ height: '26px', fontSize: '11px' }}
                              value={b}
                              onChange={(e) => {
                                const nextProjs = [...profileData.projects];
                                const nextBullets = [...(nextProjs[projIdx].bullets || [])];
                                nextBullets[bulletIdx] = e.target.value;
                                nextProjs[projIdx] = { ...nextProjs[projIdx], bullets: nextBullets };
                                updateProfileField('projects', nextProjs);
                              }}
                              placeholder="Project bullet..."
                            />
                            <button
                              type="button"
                              className="btn btn-outline btn-xs"
                              style={{ height: '26px', padding: '0 6px' }}
                              onClick={() => {
                                const nextProjs = [...profileData.projects];
                                const nextBullets = (nextProjs[projIdx].bullets || []).filter((_: any, i: number) => i !== bulletIdx);
                                nextProjs[projIdx] = { ...nextProjs[projIdx], bullets: nextBullets };
                                updateProfileField('projects', nextProjs);
                              }}
                            >
                              ✕
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          className="btn btn-outline btn-xs"
                          style={{ alignSelf: 'flex-start', height: '24px', fontSize: '10px' }}
                          onClick={() => {
                            const nextProjs = [...profileData.projects];
                            const nextBullets = [...(nextProjs[projIdx].bullets || []), ''];
                            nextProjs[projIdx] = { ...nextProjs[projIdx], bullets: nextBullets };
                            updateProfileField('projects', nextProjs);
                          }}
                        >
                          + Add Bullet
                        </button>
                      </div>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="btn btn-outline btn-xs"
                    style={{ alignSelf: 'flex-start' }}
                    onClick={() => {
                      const next = [...profileData.projects, { name: '', bullets: [] }];
                      updateProfileField('projects', next);
                    }}
                  >
                    + Add Project
                  </button>
                </div>
              </div>
            )}
            {profileUnsaved && (
              <div style={{ fontSize: 11, color: 'var(--amber)', fontWeight: 600 }}>
                Notice: You have unsaved profile changes. Remember to recompute embeddings after saving!
              </div>
            )}
            {profile?.has_embedding === false && (
              <div style={{ fontSize: 11, color: 'var(--red)', fontWeight: 600 }}>
                Notice: Embeddings are stale/missing. Tap 'Recompute Embeddings' to update the matcher cache.
              </div>
            )}
          </section>

          {/* Section 2: Target Companies */}
          <section id="target-companies" className="card flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>Target Companies</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Manage mapped ATS systems and target career URLs</p>
              </div>
              <button className="btn btn-primary btn-xs" onClick={saveCompanies} disabled={savingSection === 'companies'}>
                {savingSection === 'companies' ? 'Saving...' : 'Save Companies'}
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
                          <option value="ashby">Ashby</option>
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
              Add Row
            </button>
          </section>

          {/* Section 3: Thresholds & Caps */}
          <section id="thresholds" className="card flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>Thresholds & Caps</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Configure match parameters and system safeguards</p>
              </div>
              <button className="btn btn-primary btn-xs" onClick={saveThresholds} disabled={savingSection === 'thresholds'}>
                {savingSection === 'thresholds' ? 'Saving...' : 'Save Settings'}
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
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>Platform Toggles</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Enable/disable crawling sources instantly</p>
              </div>
              <button className="btn btn-primary btn-xs" onClick={saveToggles} disabled={savingSection === 'toggles'}>
                {savingSection === 'toggles' ? 'Saving...' : 'Save Toggles'}
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
                <h3 style={{ fontSize: 14, fontWeight: 700 }}>Screening Answers</h3>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Structured JSON feeding the form-filling engine</p>
              </div>
              <button className="btn btn-primary btn-xs" onClick={saveAnswers} disabled={savingSection === 'answers'}>
                {savingSection === 'answers' ? 'Saving...' : 'Save Answers'}
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
            <h3 style={{ fontSize: 14, fontWeight: 700 }}>Telegram Bot Connection</h3>
            <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Pair the automation center with your private chat ID</p>

            <div className="flex items-center gap-3" style={{ marginTop: 4 }}>
              <button className="btn btn-outline btn-xs" onClick={getPairToken}>
                Generate Pairing Token
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
