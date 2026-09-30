# WealthGuide

A financial snapshot in. A clear next step out.

WealthGuide turns a financial snapshot into an explainable monthly plan. Python calculates the amounts; OpenAI explains the result. PostgreSQL keeps snapshots, versioned analyses, and user feedback together.

## Build scope

- React + TypeScript interface with snapshot entry, recommendations, history, and feedback.
- FastAPI JSON API with exact decimal calculations and approved source links.
- PostgreSQL relational records and JSONB snapshots.
- One bounded OpenAI Responses call per analysis, with a deterministic fallback.
- Anonymous browser sessions for synthetic demo data; no bank connections or money movement.
- Opt-in feedback for future, human-reviewed improvements. No autonomous training.

This is an independent educational portfolio project, not a Chase product or a financial adviser. The running demo is local only. Full setup and verification instructions will be added as implementation lands.
