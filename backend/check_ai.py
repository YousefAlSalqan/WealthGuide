"""Opt-in live smoke check. Prints status only, never keys or financial payloads."""
import sys
from datetime import date
from unittest.mock import patch

from openai import OpenAI, OpenAIError

from app import ai, settings
from app.engine import build_plan
from app.models import Snapshot


if __name__ == "__main__":
    if "--live" not in sys.argv:
        raise SystemExit("Add --live to make one billable synthetic explanation request.")
    if not settings.get_api_key():
        raise SystemExit("No API key configured.")
    plan = build_plan(Snapshot(as_of=date.today(), cash_balance="5000", monthly_income="4000",
                              essential_expenses="2200", discretionary_expenses="600", emergency_fund="1500"))
    client = OpenAI(api_key=settings.get_api_key(), timeout=20, max_retries=0)
    parse = client.responses.parse

    def checked_call(*args, **kwargs):
        try:
            return parse(*args, **kwargs)
        except OpenAIError as exc:
            allowed_codes = {"insufficient_quota", "invalid_api_key", "rate_limit_exceeded", "model_not_found"}
            code = exc.code if getattr(exc, "code", None) in allowed_codes else "unclassified"
            print(f"Provider error: {type(exc).__name__}; HTTP {getattr(exc, 'status_code', 'n/a')}; code {code}")
            raise

    with patch.object(client.responses, "parse", side_effect=checked_call), patch.object(ai, "OpenAI", return_value=client):
        _, status, model = ai.explain(plan)
    print(f"Explanation: {status}; model: {model or 'none'}")
    raise SystemExit(0 if status == "generated" else 1)
