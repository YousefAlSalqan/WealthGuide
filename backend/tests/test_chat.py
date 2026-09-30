import json
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app import chat
from app.engine import build_plan
from test_core import example


def complete_draft():
    return chat.Draft(cash_balance="6400", monthly_income="4200", essential_expenses="2200",
                      discretionary_expenses="600", emergency_fund="1500", debts=[])


class ChatChecks(unittest.TestCase):
    def test_missing_is_not_zero_and_ready_requires_consistent_snapshot(self):
        partial = chat.draft_review(chat.Draft(monthly_income="4200"))
        self.assertIsNone(partial["snapshot"])
        self.assertIsNone(partial["draft"]["emergency_fund"])
        self.assertTrue(any("Debts" in item for item in partial["missing_fields"]))
        ready = chat.draft_review(complete_draft())
        self.assertEqual(ready["snapshot"]["emergency_months"], 3)
        self.assertEqual(ready["snapshot"]["monthly_income"], "4200")
        invalid = complete_draft().model_copy(update={"cash_balance": Decimal("10")})
        self.assertIsNone(chat.draft_review(invalid)["snapshot"])
        self.assertTrue(chat.draft_review(invalid)["review_issues"])

    def test_extraction_does_not_introduce_unquoted_amounts(self):
        chat.check_extracted_numbers(chat.Draft(monthly_income="4200"), chat.Draft(), "I take home $4,200 each month.")
        with self.assertRaises(ValueError):
            chat.check_extracted_numbers(chat.Draft(monthly_income="9000"), chat.Draft(), "I take home 4200.")
        with self.assertRaises(ValueError):
            chat.check_extracted_numbers(chat.Draft(monthly_income="5000"), chat.Draft(), "I earn 5k.")
        chat.check_extracted_numbers(complete_draft(), complete_draft(), "What else do you need?")

    def test_plan_response_uses_checked_placeholders_and_private_context(self):
        plan = build_plan(example())
        parsed = chat.ChatOutput(answer="Your monthly surplus is {plan_monthly_surplus}. The reserve helps with unexpected costs.",
                                 draft=chat.Draft(), source_ids=["emergency"])
        with patch("app.chat.settings.AI_ENABLED", True), patch("app.chat.settings.get_api_key", return_value="test-key"), patch("app.chat.OpenAI") as factory:
            call = factory.return_value.__enter__.return_value.responses.parse
            call.return_value = SimpleNamespace(status="completed", output_parsed=parsed, model="test-model")
            result = chat.respond("Why is the reserve first?", chat.Draft(), [], plan)
        self.assertEqual(result["ai_status"], "generated")
        self.assertIn("$1200.00", result["answer"])
        self.assertEqual(result["sources"][0]["id"], "emergency")
        sent = json.dumps(call.call_args.kwargs["input"])
        self.assertNotIn(plan["actions"][0]["id"], sent)
        self.assertFalse(call.call_args.kwargs["store"])

    def test_bad_output_keeps_previous_draft(self):
        for answer, sources in [("You can earn $9000 guaranteed.", []), ("Some advice.", ["invented-source"])]:
            output = chat.ChatOutput(answer=answer, draft=complete_draft(), source_ids=sources)
            with patch("app.chat.settings.AI_ENABLED", True), patch("app.chat.settings.get_api_key", return_value="test-key"), patch("app.chat.OpenAI") as factory:
                factory.return_value.__enter__.return_value.responses.parse.return_value = SimpleNamespace(status="completed", output_parsed=output, model="test-model")
                result = chat.respond("Why?", complete_draft(), [], None)
            self.assertEqual(result["ai_status"], "fallback")
            self.assertEqual(result["draft"], complete_draft().model_dump(mode="json"))


if __name__ == "__main__":
    unittest.main()
