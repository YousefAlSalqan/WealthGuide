import random
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from app.ai import ActionExplanation, Explanation, explain, fallback, validate_explanation
from app.engine import SOURCES, build_plan, contribution_periods
from app.models import Snapshot


def example(**changes):
    values = dict(as_of="2026-09-01", cash_balance="5000.00", monthly_income="4200.00",
                  essential_expenses="2400.00", discretionary_expenses="500.00", emergency_fund="1000.00",
                  debts=[dict(id=str(uuid4()), name="Card", balance="3200.00", apr="27.90", minimum_payment="100.00")])
    values.update(changes)
    return Snapshot.model_validate(values)


class FinancialChecks(unittest.TestCase):
    def test_known_example_and_no_double_count(self):
        plan = build_plan(example())
        self.assertEqual(plan["metrics"]["monthly_surplus"], "1200.00")
        self.assertEqual(plan["metrics"]["starter_gap"], "1500.00")
        self.assertEqual(plan["actions"][0]["amount"], "1200.00")
        self.assertEqual(plan["metrics"]["unallocated_monthly"], "0.00")

    def test_no_allocations_for_deficit_or_break_even(self):
        for income in ["2000.00", "3000.00"]:
            plan = build_plan(example(monthly_income=income))
            self.assertTrue(all(a["kind"] == "review" for a in plan["actions"]))
            self.assertEqual(plan["metrics"]["allocated_monthly"], "0.00")

    def test_avalanche_and_completed_reserve(self):
        low, high = uuid4(), uuid4()
        plan = build_plan(example(cash_balance="15000", emergency_fund="10000", debts=[
            dict(id=low, name="Lower", balance="1000", apr="12", minimum_payment="30"),
            dict(id=high, name="Higher", balance="150", apr="29", minimum_payment="50")]))
        self.assertEqual(plan["actions"][0]["id"], f"debt-{high}")
        self.assertEqual(plan["actions"][0]["amount"], "100.00")
        self.assertEqual(plan["actions"][1]["id"], f"debt-{low}")

    def test_match_cost_is_not_the_match_amount(self):
        plan = build_plan(example(emergency_fund="3000", employer_match={
            "additional_take_home_cost": "200", "additional_employer_match": "100"}))
        self.assertEqual(plan["actions"][0]["id"], "employer-match")
        self.assertEqual(plan["actions"][0]["amount"], "200.00")

    def test_reserve_never_exceeds_gap_across_both_stages(self):
        plan = build_plan(example(monthly_income="10000", debts=[]))
        reserve = sum(Decimal(a["amount"]) for a in plan["actions"] if "reserve" in a["id"])
        self.assertEqual(reserve, Decimal("6200"))

    def test_explicit_calendar_periods_and_goal(self):
        self.assertEqual(contribution_periods(date(2026, 1, 31), date(2026, 2, 28)), 1)
        self.assertEqual(contribution_periods(date(2026, 1, 31), date(2026, 3, 30)), 1)
        self.assertEqual(contribution_periods(date(2026, 1, 15), date(2027, 1, 15)), 12)
        plan = build_plan(example(as_of="2026-01-15", cash_balance="12000", emergency_fund="8000", debts=[],
                                  goal=dict(name="Course", target_amount="6000", saved_amount="1200", target_date="2027-01-15")))
        self.assertEqual(next(a for a in plan["actions"] if a["id"] == "goal")["amount"], "400.00")

    def test_invalid_cash_dates_and_decimals(self):
        for changes in [dict(emergency_fund="6000"), dict(monthly_income="NaN"), dict(monthly_income="12.345"),
                        dict(cash_balance="-1"), dict(as_of="2099-01-01"),
                        dict(goal=dict(name="Past", target_amount="10", target_date="2020-01-01"))]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                example(**changes)

    def test_allocation_invariants(self):
        rng = random.Random(42)
        source_ids = {s["id"] for s in SOURCES}
        for _ in range(150):
            cash = rng.randrange(0, 20000)
            snap = example(cash_balance=str(cash), emergency_fund=str(rng.randrange(cash + 1)),
                           monthly_income=str(rng.randrange(0, 12000)), discretionary_expenses=str(rng.randrange(0, 2000)))
            plan = build_plan(snap)
            self.assertEqual(plan, build_plan(snap))
            allocations = sum((Decimal(a["amount"]) for a in plan["actions"]), Decimal(0))
            self.assertLessEqual(allocations, max(Decimal(plan["metrics"]["monthly_surplus"]), 0))
            self.assertEqual(allocations + Decimal(plan["metrics"]["unallocated_monthly"]), max(Decimal(plan["metrics"]["monthly_surplus"]), 0))
            self.assertTrue(all(set(a["source_ids"]) <= source_ids and a["source_ids"] for a in plan["actions"]))

    def test_ai_placeholders_and_rejection(self):
        plan = build_plan(example())
        prose = Explanation(headline="A clearer path", summary="Your monthly capacity is {monthly_surplus}.",
                            actions=[ActionExplanation(action_id=a["id"], explanation="Set aside {action_amount} as your next step.") for a in plan["actions"]])
        self.assertIn("$1200.00", validate_explanation(prose, plan)["summary"])
        for bad in ["Save $9999.", "Expect guaranteed growth.", "Use {invented}."]:
            prose.summary = bad
            with self.assertRaises(ValueError):
                validate_explanation(prose, plan)
        with patch("app.settings.AI_ENABLED", False):
            result, status, _ = explain(plan)
        self.assertEqual(result, fallback(plan))
        self.assertEqual(status, "template")


if __name__ == "__main__":
    unittest.main()
