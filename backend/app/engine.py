"""Monthly planning only: existing cash is never allocated a second time."""
import calendar
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .models import Snapshot

RULES_VERSION = "1.0.0"
SOURCES_VERSION = "2026-09-30"
CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HIGH_APR = Decimal("10")  # Disclosed product heuristic, not a universal financial rule.
SOURCES = json.loads(Path(__file__).with_name("guidance.json").read_text(encoding="utf-8"))


def money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def contribution_periods(start: date, end: date) -> int:
    """Monthly deposits on the start-day anniversary, clipped to month end."""
    count = (end.year - start.year) * 12 + end.month - start.month
    anniversary = date(end.year, end.month, min(start.day, calendar.monthrange(end.year, end.month)[1]))
    return max(1, count - (anniversary > end))


def build_plan(snapshot: Snapshot) -> dict:
    minimums = sum((min(d.minimum_payment, d.balance) for d in snapshot.debts), ZERO)
    obligations = snapshot.essential_expenses + minimums
    spending = obligations + snapshot.discretionary_expenses
    surplus = snapshot.monthly_income - spending
    starter_gap = max(obligations - snapshot.emergency_fund, ZERO)
    target = obligations * snapshot.emergency_months
    full_gap = max(target - snapshot.emergency_fund, ZERO)
    remaining = max(surplus, ZERO)
    actions: list[dict] = []
    warnings: list[str] = []

    def action(identifier, title, requested, reason, calculation, sources, kind="allocation"):
        nonlocal remaining
        amount = min(max(requested, ZERO), remaining) if kind == "allocation" else ZERO
        if kind == "allocation" and amount == 0:
            return
        remaining -= amount
        actions.append({"id": identifier, "priority": len(actions) + 1, "title": title,
                        "amount": money(amount), "period": "monthly", "kind": kind,
                        "reason": reason, "calculation": calculation, "source_ids": sources})

    if surplus <= ZERO:
        action("stabilize", "Make room in your monthly budget", ZERO,
               "Your current spending leaves no money for new contributions. Review flexible expenses and income before adding savings or extra debt payments.",
               f"${money(snapshot.monthly_income)} income - ${money(spending)} commitments = ${money(surplus)}", ["budget"], "review")
    else:
        action("starter-reserve", "Build your first month of breathing room", starter_gap,
               "An accessible reserve can help cover an unexpected expense without adding new debt.",
               f"${money(obligations)} starter target - ${money(snapshot.emergency_fund)} reserved = ${money(starter_gap)} gap", ["emergency"])
        reserve_added = sum((Decimal(a["amount"]) for a in actions), ZERO)
        match = snapshot.employer_match
        if match and match.additional_employer_match > 0:
            if remaining >= match.additional_take_home_cost:
                action("employer-match", "Review your available employer match", match.additional_take_home_cost,
                       "Use your confirmed payroll estimate to check whether you can afford the contribution that unlocks the additional match. Verify eligibility and vesting with your employer.",
                       f"User-confirmed take-home cost ${money(match.additional_take_home_cost)}; potential employer contribution ${money(match.additional_employer_match)} per month", ["match"])
            else:
                warnings.append("The remaining budget cannot cover the confirmed take-home cost of the full employer match; no partial match is assumed.")
        high_debts = sorted((d for d in snapshot.debts if d.apr >= HIGH_APR and d.balance > 0), key=lambda d: (-d.apr, str(d.id)))
        for debt in high_debts:
            # Conservative cap: the minimum is already budgeted. No exact payoff is promised.
            extra_cap = max(debt.balance - min(debt.minimum_payment, debt.balance), ZERO)
            action(f"debt-{debt.id}", f"Pay extra toward {debt.name}", extra_cap,
                   "After covering all minimum payments, direct extra money to this higher-interest debt. Interest and lender payment rules may affect your final payoff amount.",
                   f"{debt.apr}% APR; ${money(debt.balance)} balance; ${money(debt.minimum_payment)} minimum already budgeted", ["debt"])
        action("full-reserve", "Give your emergency fund a stronger foundation", max(full_gap - reserve_added, ZERO),
               "Build toward your chosen reserve target. The right cushion depends on income stability and essential commitments.",
               f"${money(obligations)} commitments × {snapshot.emergency_months} months - ${money(snapshot.emergency_fund + reserve_added)} reserved after the first step", ["emergency"])
        if snapshot.goal:
            goal = snapshot.goal
            gap = max(goal.target_amount - goal.saved_amount, ZERO)
            periods = contribution_periods(snapshot.as_of, goal.target_date)
            needed = (gap / periods).quantize(CENT, rounding=ROUND_HALF_UP)
            if needed > remaining:
                warnings.append("Your goal needs more per month than remains after higher priorities; consider a later deadline or a smaller target.")
            action("goal", f"Make progress toward {goal.name}", needed,
                   "Set aside a regular contribution toward this goal. This estimate assumes no interest or investment returns.",
                   f"(${money(goal.target_amount)} target - ${money(goal.saved_amount)} saved) ÷ {periods} contribution periods = ${money(needed)} per period", ["goals"])
        if remaining > 0:
            action("long-term", "Explore your next long-term goal", ZERO,
                   "You have unallocated monthly capacity. Review your time horizon, remaining debt, and risk tolerance before choosing how to use it. No investment or expected return is selected here.",
                   f"${money(remaining)} remains unallocated after this plan", ["investing"], "review")
    for debt in snapshot.debts:
        if debt.balance > 0 and debt.minimum_payment <= debt.balance * debt.apr / 100 / 12:
            warnings.append(f"The entered minimum for {debt.name} may not cover a simplified month's interest. Confirm it with your lender.")
    if snapshot.cash_balance - snapshot.emergency_fund - (snapshot.goal.saved_amount if snapshot.goal else ZERO) < obligations:
        warnings.append("Your unreserved cash is below one month of essential commitments. Check bill and payday timing before acting; this snapshot is not a daily cash-flow forecast.")
    source_ids = {source for a in actions for source in a["source_ids"]}
    return {
        "metrics": {"monthly_surplus": money(surplus), "monthly_commitments": money(spending),
                    "minimum_debt_payments": money(minimums), "emergency_target": money(target),
                    "emergency_gap": money(full_gap), "starter_gap": money(starter_gap),
                    "allocated_monthly": money(max(surplus, ZERO) - remaining), "unallocated_monthly": money(remaining),
                    "total_debt": money(sum((d.balance for d in snapshot.debts), ZERO))},
        "actions": actions, "warnings": warnings,
        "sources": [s for s in SOURCES if s["id"] in source_ids],
        "assumptions": [
            "Amounts are USD and monthly. Take-home income already excludes existing payroll deductions.",
            "Cash includes emergency and goal savings; these are separate earmarked portions, not additional cash.",
            "Expenses exclude the listed debt minimums, which are deducted once. Proposed new savings are not included in expenses.",
            "Only future monthly surplus is allocated. Existing cash is not recommended for immediate transfers.",
            "The one-month starter reserve and 10% high-interest cutoff are transparent MVP heuristics, not Chase rules or a universal optimum.",
            "Goals use end-of-period monthly contributions, with at least one period for a near-term goal. There are no assumed returns."],
        "rules_version": RULES_VERSION, "sources_version": SOURCES_VERSION,
    }
