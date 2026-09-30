# Calculation rules v1.0.0

These are transparent educational product heuristics, not personalized professional advice or an algorithm supplied by Chase. Sources explain concepts; Python `Decimal` code defines arithmetic. Values round half-up to cents.

## Accounting

- Total cash includes separate emergency and goal savings. Their sum cannot exceed cash, and they are never counted twice.
- Take-home income excludes existing payroll deductions. Expenses exclude listed debt minimums and proposed new savings.
- Budgeted debt minimum = `min(entered minimum, balance)`; verify actual lender billing separately.
- Essential commitments = essentials + debt minimums.
- Monthly surplus = income − essential commitments − flexible expenses.
- Starter reserve = one month of essential commitments. Full reserve = chosen months × essential commitments (default three; allowed one through twelve).
- Only positive future monthly surplus is allocated. Existing cash is not assigned to immediate transfers.

## Allocation order

1. For zero/negative surplus, recommend budget review; no new contributions.
2. Fill the one-month starter-reserve gap, capped by surplus.
3. If provided and fully affordable, budget the confirmed additional take-home cost to unlock the employer match. Match dollars are not assumed to equal the cost. If unaffordable, flag it without assuming partial benefits.
4. Pay extra toward debts at/above the **10% APR heuristic**, highest rate first. Cap each extra payment by available surplus and `balance − budgeted minimum`. This is conservative, not an exact payoff quote; interest and lender rules matter.
5. Fill the full-reserve gap, subtracting existing savings and the starter allocation already made in this plan.
6. Save toward the optional goal: `max(target − saved, 0) / contribution periods`, rounded to cents and capped by remaining surplus. Warn if the required contribution does not fit.
7. Leave remaining surplus unallocated and suggest reviewing time horizon, remaining debt and risk tolerance. No securities or expected returns are selected.

Contribution periods end on monthly anniversaries of the snapshot day, clipped to month-end. Count those up to the deadline, with a minimum of one period for a near-term goal. No returns are assumed. Rounding may require a final adjustment of a few cents; this is not an executed payment schedule.

Warnings flag insufficient unreserved cash for essential commitments and entered minimums at/below a simplified monthly interest estimate (`balance × APR / 100 / 12`). Neither is an exact lender-interest or daily cash-flow forecast.

## Example

Income $4,200, essentials $2,200, flexible expenses $600, debt minimum $100: **$1,300 surplus**. With $1,500 reserved, the starter target is $2,300: assign **$800** to the reserve and **$500** extra to the 24.9% APR card. Total allocations never exceed $1,300. Original cash stays untouched.

## AI boundary

The model receives completed metrics, generic rationales and curated summaries. It cannot modify the saved plan. Structured output supplies the headline, summary and ordered explanations. Prose numbers use server-replaced placeholders. Unknown action IDs, numeric literals, excessive lengths and selected prohibited claims trigger fallback.

These checks do not prove every possible sentence is semantically correct. Human-reviewed evaluation and additional controls are required for real financial use. The UI retains authoritative amounts, formulas, assumptions and source links.
