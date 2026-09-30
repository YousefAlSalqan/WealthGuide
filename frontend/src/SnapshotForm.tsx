import { ArrowRight, Plus, Trash2, Sparkles, ShieldCheck, Wallet, TrendingUp, CircleHelp } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import type { Snapshot } from './types'

export const today = () => new Date().toLocaleDateString('en-CA')
export const formatMoney = (n: string | number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(Number(n) || 0)
const inOneYear = () => { const d = new Date(); d.setFullYear(d.getFullYear() + 1); return d.toLocaleDateString('en-CA') }

export function sampleSnapshot(): Snapshot {
  return { as_of: today(), currency: 'USD', cash_balance: '6400', monthly_income: '4200', essential_expenses: '2200', discretionary_expenses: '600',
    emergency_fund: '1500', emergency_months: 3,
    debts: [{ id: crypto.randomUUID(), name: 'Credit card', balance: '3200', apr: '24.9', minimum_payment: '100' }],
    goal: null, employer_match: null }
}

function MoneyInput({ label, value, onChange, hint, suffix = '$' }: { label: string; value: string; onChange: (value: string) => void; hint?: string; suffix?: string }) {
  return <label className="field"><span className="field-label">{label}</span><span className="money-input"><span aria-hidden="true">{suffix}</span><input aria-label={label} required inputMode="decimal" type="number" min="0" max="100000000" step="0.01" value={value} onChange={e => onChange(e.target.value)} /></span>{hint && <span className="field-hint">{hint}</span>}</label>
}

export default function SnapshotForm({ initial, busy, onSubmit }: { initial: Snapshot; busy: boolean; onSubmit: (snapshot: Snapshot) => void }) {
  const [form, setForm] = useState<Snapshot>(initial)
  const update = <K extends keyof Snapshot>(key: K, value: Snapshot[K]) => setForm(f => ({ ...f, [key]: value }))
  const minimums = form.debts.reduce((sum, d) => sum + Math.min(Number(d.minimum_payment), Number(d.balance)), 0)
  const commitments = Number(form.essential_expenses) + Number(form.discretionary_expenses) + minimums
  const surplus = Number(form.monthly_income) - commitments
  const percent = Math.min(100, Math.max(0, commitments / Math.max(Number(form.monthly_income), 1) * 100))
  function submit(e: FormEvent) { e.preventDefault(); onSubmit(form) }

  return <div className="snapshot-layout">
    <form className="snapshot-form" onSubmit={submit}>
      <fieldset disabled={busy}>
        <section className="panel form-section">
          <div className="section-title"><div><h2>Your starting point</h2><p>A few numbers help us see the whole picture.</p></div><button type="button" className="text-button sample-button" onClick={() => setForm(sampleSnapshot())}><Sparkles size={14} /> Use sample</button></div>
          <div className="field-grid">
            <MoneyInput label="Total cash balance" value={form.cash_balance} onChange={v => update('cash_balance', v)} hint="Checking + savings, including the reserves below." />
            <MoneyInput label="Monthly take-home income" value={form.monthly_income} onChange={v => update('monthly_income', v)} hint="After tax and existing payroll contributions." />
            <MoneyInput label="Emergency savings" value={form.emergency_fund} onChange={v => update('emergency_fund', v)} hint="The part of your cash set aside for surprises." />
            <label className="field"><span className="field-label">Snapshot date</span><input aria-label="Snapshot date" type="date" required max={today()} value={form.as_of} onChange={e => update('as_of', e.target.value)} /><span className="field-hint">The date these numbers reflect.</span></label>
          </div>
        </section>
        <section className="panel form-section">
          <div className="section-title"><div><h2>What goes out each month</h2><p>Leave debt payments out. We’ll add those separately.</p></div></div>
          <div className="field-grid">
            <MoneyInput label="Essential expenses" value={form.essential_expenses} onChange={v => update('essential_expenses', v)} hint="Rent, groceries, transport, utilities and insurance." />
            <MoneyInput label="Flexible spending" value={form.discretionary_expenses} onChange={v => update('discretionary_expenses', v)} hint="Dining out, subscriptions and other non-essentials." />
          </div>
          <div className="debt-heading"><h3>Debts <span className="optional">Optional</span></h3><button type="button" className="text-button" disabled={form.debts.length >= 20} onClick={() => update('debts', [...form.debts, { id: crypto.randomUUID(), name: '', balance: '', apr: '', minimum_payment: '' }])}><Plus size={15} /> Add debt</button></div>
          {form.debts.map((debt, i) => <div className="debt-row" key={debt.id}>
            <label className="field debt-name"><span className="field-label">Debt name</span><input aria-label={`Debt name ${i + 1}`} required maxLength={60} value={debt.name} onChange={e => update('debts', form.debts.map(d => d.id === debt.id ? { ...d, name: e.target.value } : d))} /></label>
            {(['balance', 'apr', 'minimum_payment'] as const).map(key => <MoneyInput key={key} label={`${key === 'balance' ? 'Balance' : key === 'apr' ? 'APR' : 'Minimum / month'} ${i + 1}`} suffix={key === 'apr' ? '%' : '$'} value={debt[key]} onChange={v => update('debts', form.debts.map(d => d.id === debt.id ? { ...d, [key]: v } : d))} />)}
            <button type="button" className="icon-button remove-debt" aria-label={`Remove ${debt.name || 'debt'}`} onClick={() => update('debts', form.debts.filter(d => d.id !== debt.id))}><Trash2 size={16} /></button>
          </div>)}
          {form.debts.length === 0 && <p className="quiet-note">No debt added. You can still create a plan.</p>}
        </section>
        <section className="panel form-section">
          <div className="section-title"><div><h2>Something to work toward</h2><p>Make your plan fit the life you’re building.</p></div></div>
          <div className="reserve-setting"><label htmlFor="reserve">Emergency cushion</label><select id="reserve" value={form.emergency_months} onChange={e => update('emergency_months', Number(e.target.value))}>{[1, 2, 3, 4, 5, 6, 9, 12].map(n => <option key={n} value={n}>{n} {n === 1 ? 'month' : 'months'} of essentials</option>)}</select></div>
          <label className="toggle-row"><input type="checkbox" checked={!!form.goal} onChange={e => update('goal', e.target.checked ? { name: '', target_amount: '', saved_amount: '0', target_date: inOneYear() } : null)} /><span>Add a personal savings goal</span></label>
          {form.goal && <div className="field-grid inset-fields"><label className="field"><span className="field-label">Goal name</span><input required maxLength={60} value={form.goal.name} onChange={e => update('goal', { ...form.goal!, name: e.target.value })} placeholder="A course, a move, a new beginning…" /></label><MoneyInput label="Goal amount" value={form.goal.target_amount} onChange={v => update('goal', { ...form.goal!, target_amount: v })} /><MoneyInput label="Already saved for this goal" value={form.goal.saved_amount} onChange={v => update('goal', { ...form.goal!, saved_amount: v })} hint="Part of your total cash, separate from emergency savings." /><label className="field"><span className="field-label">Target date</span><input required type="date" min={form.as_of} value={form.goal.target_date} onChange={e => update('goal', { ...form.goal!, target_date: e.target.value })} /></label></div>}
          <details className="match-details"><summary>Employer retirement match <span className="optional">Optional</span></summary><p>Use a payroll estimate from your employer. These fields don’t calculate taxes or assume how much you must contribute.</p><label className="toggle-row"><input type="checkbox" checked={!!form.employer_match} onChange={e => update('employer_match', e.target.checked ? { additional_take_home_cost: '', additional_employer_match: '' } : null)} /><span>I know the extra take-home cost and match</span></label>{form.employer_match && <div className="field-grid"><MoneyInput label="Monthly take-home reduction" value={form.employer_match.additional_take_home_cost} onChange={v => update('employer_match', { ...form.employer_match!, additional_take_home_cost: v })} /><MoneyInput label="Additional employer match" value={form.employer_match.additional_employer_match} onChange={v => update('employer_match', { ...form.employer_match!, additional_employer_match: v })} /></div>}</details>
        </section>
        <div className="submit-row"><p><ShieldCheck size={16} /> Demo data, thoughtfully handled.</p><button className="button primary" type="submit">{busy ? 'Creating your plan…' : <>Create my plan <ArrowRight size={17} /></>}</button></div>
      </fieldset>
    </form>
    <aside className="snapshot-aside">
      <div className="picture-card"><h2><Wallet size={18} />Your monthly picture</h2><p className="picture-label">Room to make progress</p><div className={`picture-amount ${surplus < 0 ? 'negative' : ''}`}>{formatMoney(surplus)}<span>/ mo</span></div><p className="picture-description">{surplus > 0 ? 'A starting point for your next good money decision.' : 'Let’s look for a little breathing room in your budget.'}</p><div className="budget-track" aria-hidden="true"><span style={{ width: `${percent}%` }} /></div><div className="budget-legend"><span><i />Commitments</span><span><i />Available</span></div><div className="picture-line"><span>Take-home income</span><strong>{formatMoney(form.monthly_income)}</strong></div><div className="picture-line"><span>Monthly commitments</span><strong>− {formatMoney(commitments)}</strong></div><div className="picture-footnote">Live preview · Your final plan is checked by the API.</div></div>
      <div className="aside-note"><span className="note-icon"><TrendingUp size={19} /></span><h3>Small steps. Real direction.</h3><p>Your plan puts the basics first, then helps you build a cushion, reduce debt and work toward your goals.</p></div>
      <div className="aside-note muted-note"><CircleHelp size={17} /><p>Emergency and goal savings are already part of your total cash. We’ll never count the same money twice.</p></div>
    </aside>
  </div>
}
