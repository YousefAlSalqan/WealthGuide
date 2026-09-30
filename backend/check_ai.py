"""Opt-in live smoke check. Prints status only, never keys or financial payloads."""
import sys
from datetime import date
from unittest.mock import patch

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from app import ai, chat, settings
from app.engine import build_plan
from app.models import Snapshot


if __name__ == "__main__":
    if "--live" not in sys.argv:
        raise SystemExit("Add --live for one billable synthetic explanation, or --live --chat for two chat requests.")
    if not settings.get_api_key():
        raise SystemExit("No API key configured.")
    plan = build_plan(Snapshot(as_of=date.today(), cash_balance="5000", monthly_income="4000",
                              essential_expenses="2200", discretionary_expenses="600", emergency_fund="1500"))
    def checked_client(**kwargs):
        client = OpenAI(**kwargs)
        parse = client.responses.parse

        def checked_call(*args, **kwargs):
            try:
                return parse(*args, **kwargs)
            except OpenAIError as exc:
                allowed_codes = {"insufficient_quota", "invalid_api_key", "rate_limit_exceeded", "model_not_found", "invalid_json_schema"}
                code = exc.code if getattr(exc, "code", None) in allowed_codes else "unclassified"
                print(f"Provider error: {type(exc).__name__}; HTTP {getattr(exc, 'status_code', 'n/a')}; code {code}")
                raise
            except ValueError as exc:
                print(f"Structured output rejected: {type(exc).__name__}")
                if isinstance(exc, ValidationError):
                    print("Invalid fields: " + ", ".join(f"{e['loc']}: {e['type']}" for e in exc.errors()))
                raise

        client.responses.parse = checked_call
        return client

    if "--chat" in sys.argv:
        message = ("My current total cash is 6400 USD, including 1500 USD in emergency savings. "
                   "My monthly take-home income is 4200 USD. Monthly essentials are 2200 USD and flexible spending "
                   "is 600 USD, excluding debt payments and savings. My only debt is a credit card with "
                   "a 3200 USD balance, 24.9 percent APR and a 100 USD monthly minimum.")
        with patch.object(chat, "OpenAI", side_effect=checked_client):
            intake = chat.respond(message, chat.Draft(), [], None)
            print(f"Chat intake: {intake['ai_status']}; review ready: {bool(intake['snapshot'])}; model: {intake['model_version'] or 'none'}")
            assert intake["ai_status"] == "generated" and intake["snapshot"], "Live intake failed"
            snapshot = Snapshot.model_validate(intake["snapshot"])
            plan = build_plan(snapshot)
            assert plan["metrics"]["monthly_surplus"] == "1300.00", "Unexpected intake calculation"
            followup = chat.respond("How much is my monthly surplus, and why is my first step the priority?",
                                    chat.Draft.model_validate(intake["draft"]), [{"message": message, "result": intake}], plan)
            print(f"Plan question: {followup['ai_status']}; model: {followup['model_version'] or 'none'}")
            assert followup["ai_status"] == "generated" and "$1300.00" in followup["answer"], "Live plan question failed"
            assert followup["draft"] == intake["draft"], "Plan question changed the intake draft"
    else:
        with patch.object(ai, "OpenAI", side_effect=checked_client):
            _, status, model = ai.explain(plan)
        print(f"Explanation: {status}; model: {model or 'none'}")
        raise SystemExit(0 if status == "generated" else 1)
