import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ArrowUpRight, BookOpen, CheckCircle2, ChevronRight, Clock3, Download, FileText, History, LayoutDashboard, Leaf, LockKeyhole, Menu, Plus, ShieldCheck, Trash2, X } from 'lucide-react'
import { api, ensureSession, errorMessage, getSession, saveSession } from './api'
import PlanView from './PlanView'
import SnapshotForm, { formatMoney, sampleSnapshot } from './SnapshotForm'
import type { Analysis, Feedback, HistoryItem, Session, Snapshot, Source } from './types'

type Page = 'snapshot' | 'plan' | 'history' | 'learn' | 'privacy'
const pageNames: Record<Page, string> = { snapshot: 'Financial snapshot', plan: 'Your plan', history: 'Plan history', learn: 'Learning library', privacy: 'Privacy & data' }
const navigation = [{ id: 'plan', title: 'Your plan', icon: LayoutDashboard }, { id: 'snapshot', title: 'Financial snapshot', icon: FileText }, { id: 'history', title: 'Plan history', icon: History }, { id: 'learn', title: 'Learning library', icon: BookOpen }] as const

export default function App() {
  const [page, setPage] = useState<Page>('snapshot')
  const [session, setUser] = useState<Session | null>(getSession())
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot>(sampleSnapshot)
  const [formKey, setFormKey] = useState(0)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [sources, setSources] = useState<Source[]>([])
  const [busy, setBusy] = useState(false)
  const [starting, setStarting] = useState(true)
  const [error, setError] = useState('')
  const [notification, setNotification] = useState('')
  const [mobileMenu, setMobileMenu] = useState(false)
  const requestRef = useRef<{ data: string; requestId: string } | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)

  async function refreshHistory(offset = 0) {
    const result = await api<{ items: HistoryItem[]; has_more: boolean }>(`/v1/analyses?offset=${offset}`)
    setHistory(old => offset ? [...old, ...result.items] : result.items); setHasMore(result.has_more)
    return result.items
  }
  useEffect(() => {
    let active = true
    async function start() {
      try {
        let current = getSession()
        if (current) {
          try { const profile = await api<{ user_id: string; improvement_opt_in: boolean }>('/v1/users/me'); current = { ...current, ...profile }; saveSession(current) }
          catch (e) { if (!getSession()) current = null; else throw e }
        }
        current ??= await ensureSession()
        if (!active) return
        setUser(current)
        const [items, catalog] = await Promise.all([refreshHistory(), api<Source[]>('/v1/guidance')])
        if (!active) return
        setSources(catalog)
        if (items[0]) {
          const latest = await api<Analysis>(`/v1/analyses/${items[0].analysis_id}`)
          if (active) { setAnalysis(latest); setSnapshot(latest.snapshot); setFormKey(k => k + 1); if (latest.status === 'complete') setPage('plan') }
        }
      } catch (e) { if (active) setError(errorMessage(e)) } finally { if (active) setStarting(false) }
    }
    start()
    return () => { active = false }
  }, [])

  function navigate(next: Page) {
    if (next === 'snapshot' && page !== 'snapshot') requestRef.current = null
    setPage(next); setMobileMenu(false); setError(''); setNotification('')
    requestAnimationFrame(() => { heading.current?.focus(); window.scrollTo({ top: 0 }) })
  }
  async function submit(value: Snapshot) {
    if (busy) return
    setBusy(true); setError(''); setSnapshot(value)
    try {
      const current = await ensureSession(); setUser(current)
      const data = JSON.stringify(value)
      if (requestRef.current?.data !== data) requestRef.current = { data, requestId: crypto.randomUUID() }
      let result = await api<Analysis>('/v1/analyses', { method: 'POST', body: JSON.stringify({ user_id: current.user_id, request_id: requestRef.current.requestId, snapshot: value }) })
      for (let i = 0; result.status === 'processing' && i < 95; i++) {
        await new Promise(resolve => setTimeout(resolve, 1000))
        result = await api<Analysis>(`/v1/analyses/${result.analysis_id}`)
      }
      setAnalysis(result); navigate('plan'); await refreshHistory()
    } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  async function openAnalysis(id: string) {
    setBusy(true); setError('')
    try { const result = await api<Analysis>(`/v1/analyses/${id}`); setAnalysis(result); navigate('plan') }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  async function saveFeedback(value: Feedback) {
    if (!analysis) return
    const saved = await api<Feedback>(`/v1/analyses/${analysis.analysis_id}/feedback`, { method: 'PUT', body: JSON.stringify(value) })
    setAnalysis(old => old ? { ...old, feedback: [...old.feedback.filter(f => f.action_id !== saved.action_id), saved] } : old)
  }
  async function optIn(value: boolean) {
    setBusy(true); setError('')
    try { const updated = await api<{ user_id: string; improvement_opt_in: boolean }>('/v1/users/me', { method: 'PATCH', body: JSON.stringify({ improvement_opt_in: value }) }); const current = { ...getSession()!, ...updated }; saveSession(current); setUser(current); setNotification('Your preference has been saved.') }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  async function exportData() {
    setBusy(true); setError('')
    try { const data = await api('/v1/users/me/export'); const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const link = document.createElement('a'); link.href = url; link.download = 'wealthguide-export.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setNotification('Your data export is ready.') }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  async function deleteData() {
    if (!window.confirm('Delete this demo session, all snapshots, plans and feedback? This cannot be undone.')) return
    setBusy(true); setError('')
    try { await api('/v1/users/me/data', { method: 'DELETE' }); saveSession(null); setUser(null); setAnalysis(null); setHistory([]); setHasMore(false); setSnapshot(sampleSnapshot()); setFormKey(k => k + 1); requestRef.current = null; setUser(await ensureSession()); navigate('snapshot'); setNotification('Your previous session and all its saved data were deleted.') }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    {mobileMenu && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMobileMenu(false)} />}
    <aside className={`sidebar ${mobileMenu ? 'open' : ''}`}><a className="brand" href="#" onClick={e => { e.preventDefault(); navigate('snapshot') }}><img src="/mark.svg" alt="" />WealthGuide<span className="brand-dot">.</span></a><div className="sidebar-section">YOUR WORKSPACE</div><nav aria-label="Main navigation">{navigation.map(item => <button key={item.id} disabled={busy} onClick={() => navigate(item.id)} className={`nav-item ${page === item.id ? 'active' : ''}`} aria-current={page === item.id ? 'page' : undefined}><item.icon size={18} />{item.title}{page === item.id && <span className="nav-dot" />}</button>)}</nav><div className="sidebar-bottom"><div className="sidebar-message"><Leaf size={23} /><h3>A little better,<br />every month.</h3><p>Good financial habits start with understanding where you are.</p></div><button disabled={busy} onClick={() => navigate('privacy')} className={`nav-item ${page === 'privacy' ? 'active' : ''}`}><ShieldCheck size={18} />Privacy & data</button><div className="profile"><span className="avatar">D</span><div><strong>Demo workspace</strong><span>Personal finance, made clear</span></div></div></div></aside>
    <div className="workspace"><header className="topbar"><div className="breadcrumbs"><button className="icon-button mobile-toggle" aria-label={mobileMenu ? 'Close menu' : 'Open menu'} onClick={() => setMobileMenu(!mobileMenu)}>{mobileMenu ? <X size={20} /> : <Menu size={20} />}</button><span>Workspace</span><ChevronRight size={13} /><strong>{pageNames[page]}</strong></div><span className="local-badge"><span />Local demo <LockKeyhole size={12} /></span></header>
      <main id="main"><div className="page-heading"><div><div className="eyebrow">A CLEARER PICTURE. A CONFIDENT NEXT STEP.</div><h1 ref={heading} tabIndex={-1}>{page === 'snapshot' ? 'Your money, with direction.' : page === 'plan' ? 'A plan that starts with you.' : page === 'history' ? 'See how far you’ve come.' : page === 'learn' ? 'A little knowledge goes a long way.' : 'Your information. Your choice.'}</h1><p>{page === 'snapshot' ? 'Start with a snapshot. We’ll help you turn it into a thoughtful next step.' : page === 'plan' ? 'Practical guidance, grounded in your numbers and explained in plain English.' : page === 'history' ? 'Every snapshot is a moment in time. Your previous plans live here.' : page === 'learn' ? 'Reliable reading for the decisions that matter to you.' : 'See what’s saved, how AI is used, and what stays in your control.'}</p></div>{page !== 'snapshot' && <button className="button secondary new-snapshot" disabled={busy} onClick={() => navigate('snapshot')}><Plus size={16} /> New snapshot</button>}</div>
      <div className="demo-notice"><ShieldCheck size={15} /><span>A space to explore. This MVP uses synthetic financial data and doesn’t connect to your bank.</span><span className="demo-chip">DEMO</span></div>
      {error && <div className="error-notice" role="alert"><strong>We couldn’t complete that step.</strong><p>{error}</p>{!getSession() && <button className="text-button" onClick={() => window.location.reload()}>Start a new session <ArrowRight size={14} /></button>}</div>}
      {notification && <p className="success-notice" role="status"><CheckCircle2 size={15} />{notification}</p>}
      {starting ? <div className="loading-state" role="status"><span className="spinner" />Opening your workspace…</div> : <>
        {page === 'snapshot' && <SnapshotForm key={formKey} initial={snapshot} busy={busy} onSubmit={submit} />}
        {page === 'plan' && (analysis ? <PlanView key={analysis.analysis_id} analysis={analysis} onFeedback={saveFeedback} onEdit={() => { setSnapshot(analysis.snapshot); setFormKey(k => k + 1); requestRef.current = null; navigate('snapshot') }} /> : <div className="panel empty-state"><Leaf size={36} /><h2>Your next chapter starts here.</h2><p>Add a few details about your finances to see your first plan.</p><button className="button primary" onClick={() => navigate('snapshot')}>Create a snapshot <ArrowRight size={16} /></button></div>)}
        {page === 'history' && <section className="panel history-panel"><div className="section-title"><span className="note-icon"><Clock3 size={18} /></span><div><h2>Your saved plans</h2><p>Past recommendations keep their original calculations and explanation.</p></div></div>{history.length === 0 ? <div className="empty-state"><History size={32} /><h3>A fresh start.</h3><p>Create your first plan to start your history.</p><button className="button primary" onClick={() => navigate('snapshot')}>Create a snapshot <ArrowRight size={15} /></button></div> : <><div className="table-wrap"><table><thead><tr><th>Created</th><th>Monthly surplus</th><th>First step</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{history.map(item => <tr key={item.analysis_id}><td><strong>{new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</strong><small>{new Date(item.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}</small></td><td className={Number(item.metrics.monthly_surplus) < 0 ? 'negative' : 'positive'}>{formatMoney(item.metrics.monthly_surplus)}</td><td>{item.top_action}<small>{item.status === 'processing' ? 'Preparing explanation' : item.ai_status === 'generated' ? 'AI explanation' : 'Standard explanation'}</small></td><td><button className="icon-button" disabled={busy} onClick={() => openAnalysis(item.analysis_id)} aria-label={`Open plan from ${new Date(item.created_at).toLocaleString()}`}><ArrowRight size={18} /></button></td></tr>)}</tbody></table></div>{hasMore && <button className="button secondary" onClick={async () => { try { await refreshHistory(history.length) } catch (e) { setError(errorMessage(e)) } }}>Load more plans</button>}</>}</section>}
        {page === 'learn' && <><div className="content-heading"><div><span className="eyebrow">UNDERSTAND THE WHY</span><h2>Good guidance, from trusted sources</h2></div><span className="subtle-label">{sources.length} curated resources</span></div><div className="source-grid">{sources.map((source, i) => <a key={source.id} className="source-card" href={source.url} target="_blank" rel="noreferrer"><div className="source-top"><span className="source-index">0{i + 1}</span><ArrowUpRight size={18} /></div><div className="eyebrow">{source.publisher}</div><h3>{source.title}</h3><p>{source.summary}</p><span className="source-link">Read the original <ArrowRight size={14} /></span></a>)}</div><p className="footnote">Original summaries with source links. WealthGuide is independent and is not affiliated with Chase, the CFPB or the IRS.</p></>}
        {page === 'privacy' && <div className="privacy-layout"><section className="panel privacy-panel"><div className="section-title"><span className="note-icon"><LockKeyhole size={19} /></span><div><h2>Built around a small financial snapshot</h2><p>Your local workspace, explained.</p></div></div><div className="privacy-row"><h3>What we save</h3><p>Your snapshots, calculated plans, explanations and feedback are saved in the local PostgreSQL database. Your browser stores only its anonymous session ID and access token. Form inputs aren’t saved until you submit them.</p></div><div className="privacy-row"><h3>What the AI sees</h3><p>Calculated metrics, generic action rationales and approved educational summaries. Your session ID, debt labels, goal name and feedback are excluded. OpenAI writes the explanation; it doesn’t decide the amounts.</p><p>Requests use <code>store: false</code>. This doesn’t eliminate the provider’s separate abuse-monitoring retention. <a href="https://developers.openai.com/api/docs/guides/your-data" target="_blank" rel="noreferrer">Read OpenAI’s data controls.</a></p></div><div className="privacy-row"><h3>A demo session, not a bank login</h3><p>A private session token separates your saved plans. There’s no password or account recovery. Use synthetic data here; keep this app on localhost.</p><span className="session-id">Session {session?.user_id.slice(0, 8)}…</span></div><div className="privacy-row"><h3>Improvement is your choice</h3><label className="toggle-row"><input type="checkbox" disabled={busy} checked={session?.improvement_opt_in || false} onChange={e => optIn(e.target.checked)} /><span>Allow my future feedback to be considered for reviewed improvements</span></label><p>Off by default. Nothing trains itself. New feedback can become an evaluation candidate only with consent and human review. Turning this off withdraws consent from previously saved feedback.</p></div><div className="data-actions"><button className="button secondary" disabled={busy} onClick={exportData}><Download size={16} />Export my data</button><button className="button danger" disabled={busy} onClick={deleteData}><Trash2 size={16} />Delete my data</button></div><p className="footnote">Data remains in your local database until you delete it. Deletion removes this session and all its related records; it cannot recall provider logs or exports you already downloaded.</p></section><div className="aside-note"><ShieldCheck size={26} /><h3>Trust is in the details.</h3><p>Every plan records the rules, prompt and model used. That makes it possible to compare changes without rewriting your financial history.</p><p>No live banking, automatic transfers, or hidden training.</p></div></div>}
      </>}
      <footer className="page-footer"><span><Leaf size={13} /> Thoughtful steps toward financial wellbeing.</span><span>Educational guidance · Not financial advice</span></footer>
      </main>
    </div>
  </div>
}
