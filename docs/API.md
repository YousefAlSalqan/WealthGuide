# API contract

Base URL: `http://localhost:8000`. The UI proxies through `http://localhost:3000/api`. Interactive documentation is at `/docs`, with the full schema at `/openapi.json`.

## Session

`POST /v1/sessions` returns `201` and `{ "user_id": "UUID", "token": "private-capability", "improvement_opt_in": false }`.

Include `Authorization: Bearer <token>` for user endpoints. The submitted user ID must match that token. A UUID alone does not authorize access. Only a SHA-256 token hash is stored in PostgreSQL. Treat the token as a password; this anonymous demo has no account recovery.

## Create a plan

`POST /v1/analyses`, JSON body:

```json
{
  "user_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "snapshot": {
    "as_of": "2026-09-30",
    "currency": "USD",
    "cash_balance": "6400.00",
    "monthly_income": "4200.00",
    "essential_expenses": "2200.00",
    "discretionary_expenses": "600.00",
    "emergency_fund": "1500.00",
    "emergency_months": 3,
    "debts": [{
      "id": "33333333-3333-4333-8333-333333333333",
      "name": "Credit card",
      "balance": "3200.00",
      "apr": "24.9",
      "minimum_payment": "100.00"
    }],
    "goal": null,
    "employer_match": null
  }
}
```

Replace `user_id` with your session ID. Generate a UUID `request_id` for each intentionally new snapshot; reuse it after a timeout. Debts need distinct UUIDs. Prefer decimal strings for money (maximum two fractional digits); responses use decimal strings. Negative money, unknown fields, non-USD currency and future snapshot dates are rejected.

First response: `201`. An identical retry returns the original analysis (`200`, or `202` if processing). Reusing its ID with different input returns `409`. Five new analyses per minute per session are allowed (`429` otherwise).

The response includes `analysis_id`, `user_id`, `request_id`, `created_at`, validated `snapshot`, computed `metrics`, ordered `actions`, `ai_explanation`, `warnings`, `assumptions`, `sources`, `feedback`, and version fields (`rules_version`, `prompt_version`, `sources_version`, `model_version`). `status` is `complete` or `processing`; `ai_status` is `generated`, `template`, `fallback` or `pending`.

Each action has an ID, priority, title, decimal amount, period, kind, rationale, visible calculation and source IDs. For the sample: surplus **$1,300**, starter reserve **$800**, extra debt payment **$500**. Original cash is not spent. AI errors never change these allocations.

Optional goal: `name`, `target_amount`, `saved_amount`, `target_date`. Optional employer match: `additional_take_home_cost`, `additional_employer_match`, both confirmed monthly amounts. The app does not infer tax effects or eligibility.

## Other endpoints

| Method and route | Behavior |
| --- | --- |
| `GET /health` | Database health and AI configuration, not proof of API credit |
| `GET /v1/users/me` | Current ID and consent |
| `PATCH /v1/users/me` | `{ "improvement_opt_in": true/false }`; opt-out revokes prior consent |
| `GET /v1/analyses?limit=20&offset=0` | Owned history, newest first; `items` and `has_more` |
| `GET /v1/analyses/{id}` | Owned saved plan; other users' IDs return `404` |
| `PUT /v1/analyses/{id}/feedback` | Upsert feedback for `overview` or a valid action ID |
| `POST /v1/scenarios` | Snapshot body; calculations only, no saving or AI |
| `GET /v1/guidance` | Public curated catalog |
| `GET /v1/users/me/export` | Owned JSON export without tokens |
| `DELETE /v1/users/me/data` | Delete current session and related records; `204` |

Feedback example: `{ "action_id": "overview", "rating": "helpful", "comment": "Clear explanation." }`. Rating: `helpful`/`not_helpful`. Action status: `accepted`/`completed`/`dismissed`. Comment limit: 500 characters. Omitted values preserve existing feedback. An explicit empty comment clears it when another feedback value is supplied. Completion is self-reported, not a verified outcome.

Validation errors return `422` with paths/messages, without echoing input. Other expected responses: `401` invalid token, `403` mismatched user ID or foreign origin, `413` body over 32 KiB, `503` database unavailable. A process interrupted after saving a plan is recovered on a later read/retry after 90 seconds using a standard explanation, without a second paid call.
