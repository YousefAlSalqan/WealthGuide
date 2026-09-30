# Privacy, security and reviewed improvement

## Storage and access

PostgreSQL stores anonymous users/token hashes, JSONB snapshots, versioned plans/explanations and feedback. Foreign keys connect them and cascade deletion. No bank credentials, real names, account numbers or transaction feeds are requested. Browser local storage holds the session ID, access token and consent preference, not financial snapshots.

Docker ports bind to loopback. Every user operation checks ownership. Same-origin proxying, origin/host checks, CSP, body limits, input validation and per-session throttling reduce demo risks. They do not replace real authentication, global spend limits or security review. Anyone holding a session token can act as that session.

Environment files (except the empty example), keys, exports and builds are Git-ignored. Build contexts exclude environment files. The optional key file is mounted read-only at runtime. Never place the server key in a `VITE_` variable, screenshot or frontend bundle.

## Provider disclosure

Calculated metrics, generic rationales and approved summaries are sent to OpenAI. User/debt IDs, debt labels, goal names and feedback are excluded. `store=False` is used, but it does **not** guarantee zero retention under separate abuse-monitoring rules. See [OpenAI's API data controls](https://developers.openai.com/api/docs/guides/your-data). The app never sends feedback for training.

One remote request per new analysis, 20-second timeout, no automatic provider retry, bounded output. Idempotency avoids a second paid call on retries. Per-session throttling is not a global budget: configure project budget alerts with the provider and keep the demo local.

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

Training jobs, dataset exports, automatic prompt edits and fine-tuning are **not implemented**. Add them only when consented, reviewed evidence and a clear evaluation objective exist.

## Before production

Add real identity and secure sessions, HTTPS, global abuse/spending controls, retention/deletion/backups, database migrations, managed secrets, monitoring without financial payloads, dependency/security review, accessibility testing and appropriate financial/legal review. Schema creation uses `CREATE TABLE IF NOT EXISTS` for a fresh MVP; it is not a migration system.
