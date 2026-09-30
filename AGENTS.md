# WealthGuide engineering notes

- Never print, stage, commit, upload, or embed `.env`, `.env.txt`, credentials, database dumps, or real financial data.
- Financial decisions and arithmetic belong in deterministic Python functions. The language model can explain but cannot alter amounts, priorities, or citations.
- Cash balance includes emergency and earmarked goal savings; never add those amounts again.
- Monthly allocations and current cash are different quantities. Never spend the same dollar twice.
- All user-owned reads and writes must verify the anonymous session token and user ownership. Demo UUIDs alone are not authorization.
- Keep the app local and use synthetic data until real authentication and deployment controls exist.
- Run backend tests and frontend type/build checks before pushing. Include regression tests for financial or access-control changes.
- Commit and push completed milestones to the user's public personal repository. Check staged files for secrets before every commit.
