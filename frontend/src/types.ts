export type Debt = { id: string; name: string; balance: string; apr: string; minimum_payment: string }
export type Goal = { name: string; target_amount: string; saved_amount: string; target_date: string }
export type Snapshot = {
  as_of: string; currency: 'USD'; cash_balance: string; monthly_income: string;
  essential_expenses: string; discretionary_expenses: string; emergency_fund: string;
  emergency_months: number; debts: Debt[]; goal: Goal | null;
  employer_match: { additional_take_home_cost: string; additional_employer_match: string } | null;
}
export type Source = { id: string; topic: string; title: string; publisher: string; url: string; summary: string; reviewed_at: string }
export type Action = { id: string; priority: number; title: string; amount: string; period: string; kind: 'allocation' | 'review'; reason: string; calculation: string; source_ids: string[] }
export type Feedback = { action_id: string; rating?: 'helpful' | 'not_helpful' | null; action_status?: 'accepted' | 'completed' | 'dismissed' | null; comment?: string; consented?: boolean }
export type Plan = {
  metrics: Record<string, string>; actions: Action[]; warnings: string[]; assumptions: string[];
  sources: Source[]; rules_version: string; sources_version: string;
}
export type Analysis = Plan & {
  analysis_id: string; user_id: string; request_id: string; snapshot: Snapshot;
  status: 'processing' | 'complete'; ai_status: 'generated' | 'template' | 'fallback' | 'pending';
  ai_explanation: { headline: string; summary: string; actions: { action_id: string; explanation: string }[] } | null;
  model_version: string | null; prompt_version: string; created_at: string; feedback: Feedback[];
}
export type HistoryItem = Pick<Analysis, 'analysis_id' | 'created_at' | 'status' | 'ai_status' | 'metrics'> & { as_of: string; top_action: string }
export type Session = { user_id: string; token: string; improvement_opt_in: boolean }
export type ChatDraft = {
  cash_balance: string | null; monthly_income: string | null; essential_expenses: string | null;
  discretionary_expenses: string | null; emergency_fund: string | null;
  debts: { name: string; balance: string | null; apr: string | null; minimum_payment: string | null }[] | null;
}
export type ChatTurn = {
  id: string; request_id: string; message: string; analysis_id: string | null; created_at: string;
  status: 'processing' | 'complete'; answer: string; draft: ChatDraft; missing_fields: string[];
  review_issues: string[]; snapshot: Snapshot | null; sources: Source[];
  ai_status: 'pending' | 'generated' | 'template' | 'fallback'; model_version: string | null; prompt_version: string;
}
