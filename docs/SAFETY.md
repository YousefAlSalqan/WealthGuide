# Privacy, security and reviewed improvement

## Storage and access

PostgreSQL stores anonymous users/token hashes, JSONB snapshots, versioned plans/explanations, feedback and chat turns. Each chat turn includes the message, answer, partial draft and optional plan association. Foreign keys connect them and cascade deletion. No bank credentials, real names, account numbers or transaction feeds are requested. Browser local storage holds the session ID, access token and consent preference, not financial snapshots or chat history.

Docker ports bind to loopback. Every user operation checks ownership. Same-origin proxying, origin/host checks, CSP, body limits, input validation and per-session throttling reduce demo risks. They do not replace real authentication, global spend limits or security review. Anyone holding a session token can act as that session.

Environment files (except the empty example), keys, exports and builds are Git-ignored. Build contexts exclude environment files. The optional key file is mounted read-only at runtime. Never place the server key in a `VITE_` variable, screenshot or frontend bundle.

## Provider disclosure

Plan explanations send calculated metrics, generic rationales and approved summaries to OpenAI; user/debt IDs, debt labels, goal names and feedback are excluded from that context. Chat additionally sends the user's raw message, last six chat turns and captured draft, including any debt labels the user supplied. Optional attached-plan context is minimized in the same way as explanations. Anything typed into chat may reach the provider: never enter credentials, account numbers or identifying information.

`store=False` is used, but it does **not** guarantee zero retention under separate abuse-monitoring rules. See [OpenAI's API data controls](https://developers.openai.com/api/docs/guides/your-data). The app never sends feedback or chat transcripts for training.

One remote request per new analysis or chat turn, 20-second timeout, no automatic provider retry, bounded output (1,500 explanation tokens or 2,000 chat tokens). Idempotency avoids a second paid call on retries. Chat allows six new messages per minute and one in-flight turn per session. Per-session throttling is not a global budget: configure project budget alerts with the provider and keep the demo local.

## Chat review boundary

Chat extracts a draft, not a financial decision. Unknown fields stay blank; debt status must be confirmed. New extracted amounts must occur numerically in the current message. Validation checks bounds, decimal precision and reserve consistency, but numerical matching is not proof that the model interpreted a fact correctly. Users must review and edit the form before explicitly creating a plan. The deterministic rules engine remains the only allocation calculator. Saved-plan questions are read-only and hypothetical calculations belong in the scenario/form tools.

Chat answers use checked placeholders for financial numbers and citations drawn only from the existing catalog. Prompt instructions prohibit invented calculations, product picks, credential requests and actions. These measures do not prove all natural-language advice is correct or make prompt injection impossible. Use synthetic data and review replies before acting. Rejected outputs and provider failures preserve the previous draft and offer the manual form.

Local data remains until deleted. Export includes only that session. Deletion cannot recall downloaded files, backups or provider logs. This project does not automatically encrypt or back up the database volume.

## Improvement groundwork shipped

- Rules, sources, prompt and model versions recorded with each analysis.
- Ratings, notes and self-reported progress attached to their original analysis/action IDs.
- Default-off consent, recorded when feedback is saved.
- Opt-out makes existing feedback ineligible. Opt-in does not retroactively consent to old feedback.
- Deterministic checks and fixed synthetic examples establish a regression baseline.

## Future reviewed improvement process

1. Select explicitly consented examples; remove personal data and review comments. Treat feedback as untrusted data, never as prompt instructions.
2. Label clarity, factual accuracy, arithmetic consistency and safety separately. A helpful vote or completed checkbox is not a financial outcome.
3. Separate development and held-out evaluation cases, including deficits, debt, reserves, goals, privacy and prompt injection.
4. Compare candidate prompts/models offline. Require no calculation/access regressions and human approval of quality and safety.
5. Version a deliberate release, monitor and retain rollback. Never rewrite history or automatically train on the model's own answers.

Training jobs, training-dataset exports, automatic prompt edits and fine-tuning are **not implemented**. Chat history is conversational memory, not self-training, and the existing feedback consent is not consent to train on transcripts. Add training only when separately consented, reviewed evidence and a clear evaluation objective exist.

## Before production

Add real identity and secure sessions, HTTPS, global abuse/spending controls, retention/deletion/backups, database migrations, managed secrets, monitoring without financial payloads, dependency/security review, accessibility testing and appropriate financial/legal review. Schema creation uses `CREATE TABLE IF NOT EXISTS` for a fresh MVP; it is not a migration system.
