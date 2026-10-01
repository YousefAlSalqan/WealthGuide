# WealthGuide

A financial snapshot in. A clear next step out.

WealthGuide turns a financial snapshot into an explainable monthly plan. Start with a form or a conversation, then ask questions about a saved plan. Python calculates the amounts; OpenAI gathers draft details and explains results. PostgreSQL keeps snapshots, versioned analyses, chats and user feedback together.

## Run it

Prerequisite: Docker Desktop with Linux containers and Docker Compose v2.24+.

```powershell
git clone https://github.com/YousefAlSalqan/WealthGuide.git
cd WealthGuide
Copy-Item .env.example .env
# Edit .env: add OPENAI_API_KEY if you want AI explanations.
docker compose up --build -d
```

Open [the app](http://localhost:3000) or [interactive API docs](http://localhost:8000/docs). New sessions open **Chat with your guide**. Describe a synthetic monthly budget, review the captured snapshot, then select **Create my plan** in the editable form. Or open **Financial snapshot** directly to try the fictional sample. Use **Ask about this plan** to attach a saved plan to chat. Without an API key, the form and calculations still work with a labeled standard explanation; chat preserves its draft and offers the form. Provider errors, timeouts and rejected output use the same fallback.

This is an independent educational portfolio project, not affiliated with JPMorganChase or a financial adviser. Use **synthetic data on localhost**, not real financial information.

In the original Windows workspace, the supplied `.env.txt` is mounted read-only as a Docker secret, selected by `OPENAI_API_KEY_FILE=.env.txt` in the ignored `.env`. The key file can contain a raw key or `OPENAI_API_KEY=...`. Do not overwrite an existing key file. Keys never enter the frontend, Docker image or Git.

```powershell
docker compose ps                 # Check service health
docker compose logs --tail 30 api  # Operational errors, not financial payloads
docker compose stop               # Stop and keep saved data
docker compose up -d              # Start again
```

PostgreSQL's named volume survives restarts, rebuilds and `docker compose down`. Do **not** add `--volumes` unless you intend to destroy all saved records. The Privacy page exports or deletes only your current session's data. Clearing browser storage loses access to the anonymous session; there is no account recovery.

## Included

- Responsive snapshot form, prioritized plan with visible math, saved history and curated learning links.
- Desktop sidebar navigation, a conversation-first workspace with a quieter snapshot summary, and light/dark/system appearance with a self-hosted Geist font. Smaller screens retain the keyboard-accessible menu. Appearance resets to the system preference on refresh; no new browser data is stored.
- Conversational snapshot intake with explicit review, plus questions about an attached, unchanged saved plan.
- Persistent chat and partial drafts, included in the session's export and deletion controls.
- Exact decimal calculations for monthly surplus, reserves, high-interest debt, savings goals and confirmed employer-match estimates.
- Unsaved spending scenarios with no extra AI call.
- One bounded, structured OpenAI Responses call per new analysis or chat turn with checked number placeholders.
- Action progress, ratings and notes, default-off improvement consent, export and deletion.
- Capability-token ownership checks, idempotent requests, input validation, local-only ports and per-session analysis throttling.

## Architecture and decisions

```text
React form → POST /api/v1/analyses → FastAPI validates snapshot
                                        ↓
                              Decimal rules → saved plan
                                        ↓
                              OpenAI explanation or fallback
                                        ↓
                              PostgreSQL → response → UI
```

Chat uses `POST /v1/chat` to persist a message and return an answer plus a draft. Only reviewing and submitting that draft through the form invokes the plan flow above. Plan questions read owned saved calculations; they cannot update an existing plan.

**PostgreSQL:** users, snapshots, analyses, feedback and chat turns have real relationships. Foreign keys, transactions, uniqueness and cascading deletion enforce them. JSONB preserves versioned snapshots, plans and chat results. The additive `chat_turns` table is created on startup without replacing existing tables. This choice is about consistency and JSON support, not a claim that SQL only scales vertically.

**Docker:** one repeatable setup for the API, PostgreSQL and web server, without a host PostgreSQL/Python installation. Docker itself is not encryption or a complete production-security solution.

**React/TypeScript + FastAPI:** typed UI and a validated, automatically documented API. No vector database, separate orchestration service or training pipeline is needed for the MVP.

**Guidance:** original summaries and links to Chase, CFPB and IRS materials in `backend/app/guidance.json`. No assumed Chase textbook API, live scraping, full-text copying or claim of an optimal financial strategy. Explicit Python code supplies the calculations, not an LLM reading a textbook.

See [API contract](docs/API.md), [calculation rules](docs/CALCULATIONS.md), and [privacy and improvement boundaries](docs/SAFETY.md).

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | empty | Server-only credential; separate API billing required |
| `OPENAI_API_KEY_FILE` | optional | Local key file instead of a dotenv key value |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Structured-output explanation and chat model |
| `AI_ENABLED` | `true` | Set `false` to avoid provider calls |
| `POSTGRES_PASSWORD` | `wealthguide-local-only` | Local demo password, not a production secret |
| `DATABASE_URL` | PostgreSQL on localhost:5433 | Host-based backend development only |

Compose sets its own database hostname. Changing `POSTGRES_PASSWORD` after the database volume is initialized does not change the existing account password; update the account deliberately instead of deleting data. Use a URL-safe password with this demo Compose template.

## Verification

With the stack running:

```powershell
docker compose run --rm -e RUN_DB_TESTS=1 -e AI_ENABLED=false api python -m unittest discover -s tests -v
cd frontend
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

Backend checks cover allocation invariants across 150 generated snapshots, rounding, reserves, goal accounting, match costs, ownership, retries, interrupted calls, consent, feedback, export, deletion and chat draft validation. Six browser checks cover desktop/mobile form and chat journeys, light/dark/system appearance, contrast tokens, keyboard navigation and widths from 320 to 1440 pixels. Screenshots of every view in both themes are saved in ignored `frontend/test-results/`. The draft-handoff browser check uses a clearly labeled AI fixture; live model checks are separate.

Browser tests use the running server's AI setting, creating one synthetic plan and one chat turn per layout. To avoid paid calls, set `AI_ENABLED=false` in `.env` and run `docker compose up -d api` before testing. Restore `true` and recreate the API afterwards. GitHub Actions runs with AI disabled and no credentials.

For an explicit live AI diagnostic, run `docker compose run --rm api python check_ai.py --live`. This makes one potentially billable synthetic request and prints only status/error codes, never keys or financial payloads. HTTP 429 means the provider rejected the request; check the API project's usage/limits and billing. A ChatGPT subscription alone does not fund API calls.

To check both real chat intake and a plan question, use `docker compose run --rm api python check_ai.py --live --chat`. This makes up to two billable synthetic chat requests and checks draft extraction and a trusted surplus placeholder; it saves no database records.

For UI development, leave Docker's API/database running and use `npm run dev` in `frontend`; open `http://localhost:5173`. Vite proxies `/api` to the backend. After source edits, `docker compose up --build -d` updates the packaged app.

Before a public commit:

```powershell
git add <specific-files>
python scripts/check_secrets.py
git diff --cached --check
```

The scanner checks Git's index for environment files and common credential patterns. It is an extra check, not a guarantee of detecting all possible secrets.

## Boundaries

No bank login, automatic transfers, security selection, return prediction or autonomous training. Public source code does **not** mean this localhost demo is ready for public hosting. Add real authentication, HTTPS, global spending/rate controls, retention/backups, migrations and security review before using real financial information.
