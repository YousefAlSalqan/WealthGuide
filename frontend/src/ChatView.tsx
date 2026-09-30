import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowRight, ArrowUpRight, CheckCircle2, FileText, MessageCircle, Send, ShieldCheck } from 'lucide-react'
import { api, errorMessage } from './api'
import { formatMoney } from './SnapshotForm'
import type { Analysis, ChatDraft, ChatTurn, Snapshot } from './types'

const fields = [
  ['cash_balance', 'Total cash'], ['monthly_income', 'Take-home / month'],
  ['essential_expenses', 'Essentials / month'], ['discretionary_expenses', 'Flexible / month'],
  ['emergency_fund', 'Emergency savings'],
] as const

export default function ChatView({ plan, availablePlan, onContext, onReview, onForm, onBusy }: {
  plan: Analysis | null; availablePlan: Analysis | null; onContext: (plan: Analysis | null) => void;
  onReview: (snapshot: Snapshot) => void; onForm: () => void; onBusy: (busy: boolean) => void;
}) {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [pendingText, setPendingText] = useState('')
  const request = useRef<{ data: string; id: string } | null>(null)
  const composer = useRef<HTMLTextAreaElement>(null)
  const transcript = useRef<HTMLDivElement>(null)
  const latest = turns.at(-1)
  const draft: ChatDraft | undefined = latest?.draft
  const captured = fields.filter(([key]) => draft?.[key] != null).length + (draft?.debts != null ? 1 : 0)

  async function completed(turn: ChatTurn) {
    for (let i = 0; turn.status === 'processing' && i < 95; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      turn = await api<ChatTurn>(`/v1/chat/${turn.id}`)
    }
    if (turn.status !== 'complete') throw new Error('The reply is still pending. Reload this page to recover it.')
    return turn
  }
  useEffect(() => {
    let active = true
    async function load() {
      try {
        const result = await api<{ items: ChatTurn[]; has_more: boolean }>('/v1/chat')
        if (!active) return
        setTurns(result.items); setHasMore(result.has_more)
        const last = result.items.at(-1)
        if (last?.status === 'processing') {
          const recovered = await completed(last)
          if (active) setTurns(old => old.map(t => t.id === recovered.id ? recovered : t))
        }
      } catch (e) { if (active) setError(errorMessage(e)) }
      finally { if (active) setLoading(false) }
    }
    load()
    return () => { active = false }
  }, [])
  useEffect(() => {
    transcript.current?.scrollTo({ top: transcript.current.scrollHeight })
  }, [turns, pendingText])

  async function send(e: FormEvent) {
    e.preventDefault()
    const text = message.trim()
    if (!text || busy || loading) return
    const data = JSON.stringify({ message: text, analysis_id: plan?.analysis_id || null })
    if (request.current?.data !== data) request.current = { data, id: crypto.randomUUID() }
    setBusy(true); onBusy(true); setError(''); setPendingText(text)
    try {
      let turn = await api<ChatTurn>('/v1/chat', { method: 'POST', body: JSON.stringify({ ...JSON.parse(data), request_id: request.current.id }) })
      turn = await completed(turn)
      setTurns(old => [...old.filter(t => t.id !== turn.id), turn]); setMessage(''); request.current = null
    } catch (e) { setError(errorMessage(e)) }
    finally { setBusy(false); onBusy(false); setPendingText(''); requestAnimationFrame(() => composer.current?.focus()) }
  }
  function prompt(text: string) { setMessage(text); composer.current?.focus() }

  return <div className="chat-layout">
    <section className="chat-panel" aria-label="Chat with WealthGuide">
      <header className="chat-header"><MessageCircle size={18} /><h2>Your WealthGuide</h2><span className="chat-ai-label">AI assistant</span></header>
      {availablePlan && <div className="chat-context"><label><input type="checkbox" checked={!!plan} disabled={busy || loading} onChange={e => onContext(e.target.checked ? availablePlan : null)} /><span>Include my selected saved plan</span></label>{plan && <p>Snapshot from {plan.snapshot.as_of} · {formatMoney(plan.metrics.monthly_surplus)} monthly surplus. The saved plan will not change.</p>}</div>}
      <div className={`chat-transcript ${!turns.length && !pendingText ? 'is-empty' : ''}`} ref={transcript} role="log" tabIndex={0} aria-label="Conversation" aria-live="polite" aria-busy={busy}>
        {!turns.length && !loading && !pendingText && <div className="chat-welcome"><div className="welcome-mark" aria-hidden="true"><img src="/mark.svg" width="42" height="42" alt="" /></div><h3>What’s on your mind?</h3><p>Start with your monthly budget, a savings question, or a step in your plan.</p></div>}
        {loading && <div className="chat-loading" role="status"><p>Opening your conversation…</p><div className="message-skeleton" aria-hidden="true"><span /><span /><span /></div></div>}
        {hasMore && <p className="chat-history-note">Showing your latest conversations. Your full chat history is included in your data export.</p>}
        {turns.map(turn => <div className="chat-turn" key={turn.id}>
          <div className="chat-bubble user"><span className="chat-speaker">You</span><p>{turn.message}</p></div>
          <div className="chat-bubble assistant"><span className="chat-speaker"><MessageCircle size={14} /> WealthGuide {turn.analysis_id && <span>· saved plan attached</span>}</span><p>{turn.status === 'processing' ? 'Preparing your reply…' : turn.answer}</p>
            {turn.status === 'complete' && <span className={`chat-response-status ${turn.ai_status === 'generated' ? '' : 'fallback'}`}>{turn.ai_status === 'generated' ? 'AI response · review before acting' : 'Standard response · AI unavailable'}</span>}
            {turn.sources.length > 0 && <div className="chat-sources">{turn.sources.map(source => <a key={source.id} href={source.url} target="_blank" rel="noreferrer">{source.publisher}: {source.title}<ArrowUpRight size={12} /></a>)}</div>}
          </div>
        </div>)}
        {pendingText && <div className="chat-turn"><div className="chat-bubble user"><span className="chat-speaker">You</span><p>{pendingText}</p></div><div className="chat-thinking" role="status"><p>Putting the details together…</p><div className="message-skeleton" aria-hidden="true"><span /><span /></div></div></div>}
      </div>
      <div className="chat-composer-area">
        {!turns.length && <div className="chat-prompts"><button disabled={busy || loading} onClick={() => prompt('Help me build my financial snapshot. What should I start with?')}><FileText size={17} /><span>Build my snapshot</span><ArrowUpRight size={14} /></button><button disabled={busy || loading} onClick={() => prompt(plan ? 'Why is the first step in my plan the priority?' : 'What is an emergency fund, and why does it matter?')}><MessageCircle size={17} /><span>{plan ? 'Explain my first step' : 'Understand the basics'}</span><ArrowUpRight size={14} /></button></div>}
        {error && <p className="error-notice" role="alert">{error}</p>}
        <form onSubmit={send} className="chat-composer"><label htmlFor="chat-message">Message your WealthGuide</label><textarea id="chat-message" ref={composer} value={message} maxLength={2000} disabled={busy || loading} onChange={e => setMessage(e.target.value)} placeholder="For example: I take home $4,200 each month…" rows={2} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }} /><div className="chat-composer-bottom"><span>Enter to send · Shift + Enter for a new line</span><button className="button primary" type="submit" disabled={busy || loading || !message.trim()} aria-label="Send message"><Send size={17} /><span>{busy ? 'Sending…' : 'Send'}</span></button></div></form>
        <p className="chat-disclosure"><ShieldCheck size={13} />Messages and drafts are saved locally. Your message, recent chat and optional plan context are sent to OpenAI. Use demo data; never share credentials or account numbers.</p>
      </div>
    </section>
    <aside className="chat-aside"><section className="panel chat-draft"><div className="section-title"><FileText size={19} /><div><h2>Your snapshot draft</h2><p>Draft only. You confirm every detail.</p></div></div>
      <p className="draft-count"><strong>{captured} of 6</strong> basics captured</p>
      <dl>{fields.map(([key, label]) => <div key={key}><dt>{label}</dt><dd className={draft?.[key] == null ? 'not-provided' : ''}>{draft?.[key] == null ? 'Not provided' : formatMoney(draft[key]!)}</dd></div>)}<div><dt>Debts</dt><dd>{draft?.debts == null ? 'Not confirmed' : draft.debts.length ? `${draft.debts.length} added` : 'None confirmed'}</dd></div></dl>
      {!!draft?.debts?.length && <div className="chat-debts">{draft.debts.map((debt, i) => <p key={i}><strong>{debt.name}</strong><span>{debt.balance == null ? 'Balance needed' : formatMoney(debt.balance)} · {debt.apr == null ? 'APR needed' : `${debt.apr}% APR`} · {debt.minimum_payment == null ? 'Minimum needed' : `${formatMoney(debt.minimum_payment)} minimum`}</span></p>)}</div>}
      {latest?.snapshot ? <p className="draft-ready"><CheckCircle2 size={15} />Ready for your review</p> : <p className="draft-hint">{latest?.review_issues[0] || 'Missing details stay blank. The guide will ask what it needs next.'}</p>}
      {!!latest?.missing_fields.length && <details className="draft-missing"><summary>What’s still needed?</summary><ul>{latest.missing_fields.map(field => <li key={field}>{field}</li>)}</ul></details>}
      <button className="button primary" disabled={busy || loading || !latest?.snapshot} onClick={() => latest?.snapshot && onReview(latest.snapshot)}>Review financial snapshot <ArrowRight size={15} /></button>
      <p className="draft-hint">You can edit amounts, add goals and choose your reserve target in the form. Nothing becomes a financial plan until you select “Create my plan.”</p>
    </section><div className="manual-entry"><span>Prefer to enter the numbers yourself?</span><button className="text-button" disabled={busy || loading} onClick={onForm}>Use the form instead <ArrowRight size={14} /></button></div></aside>
  </div>
}
