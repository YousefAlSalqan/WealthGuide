"""Integration tests use PostgreSQL and remove only sessions created by these tests."""
import os
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app, current_user, pool
from app import chat
from test_core import example
from test_chat import complete_draft


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "Set RUN_DB_TESTS=1 with PostgreSQL running")
class ApiChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai_patch = patch("app.settings.AI_ENABLED", False)
        cls.ai_patch.start()
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.ai_patch.stop()

    def setUp(self):
        self.session = self.client.post("/v1/sessions").json()
        self.headers = {"Authorization": f"Bearer {self.session['token']}"}
        self.payload = dict(user_id=self.session["user_id"], request_id=str(uuid4()), snapshot=example().model_dump(mode="json"))

    def tearDown(self):
        self.client.delete("/v1/users/me/data", headers=self.headers)

    def submit(self):
        response = self.client.post("/v1/analyses", json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_saved_analysis_retry_and_conflict(self):
        first = self.submit()
        second = self.client.post("/v1/analyses", json=self.payload, headers=self.headers)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first["analysis_id"], second.json()["analysis_id"])
        self.assertEqual(len(self.client.get("/v1/analyses", headers=self.headers).json()["items"]), 1)
        self.payload["snapshot"]["monthly_income"] = "6000"
        self.assertEqual(self.client.post("/v1/analyses", json=self.payload, headers=self.headers).status_code, 409)

    def test_ownership_and_validation(self):
        analysis = self.submit()
        other = self.client.post("/v1/sessions").json()
        other_headers = {"Authorization": f"Bearer {other['token']}"}
        try:
            self.assertEqual(self.client.get(f"/v1/analyses/{analysis['analysis_id']}", headers=other_headers).status_code, 404)
            self.assertEqual(self.client.post("/v1/analyses", json=self.payload, headers=other_headers).status_code, 403)
            self.assertEqual(self.client.get("/v1/analyses").status_code, 401)
            self.assertEqual(self.client.post("/v1/sessions", headers={"Origin": "https://untrusted.example"}).status_code, 403)
            self.payload["snapshot"]["emergency_fund"] = "999999"
            invalid = self.client.post("/v1/analyses", json=self.payload, headers=self.headers)
            self.assertEqual(invalid.status_code, 422)
            self.assertNotIn("999999", invalid.text)
        finally:
            self.client.delete("/v1/users/me/data", headers=other_headers)

    def test_feedback_consent_and_deletion(self):
        analysis = self.submit()
        path = f"/v1/analyses/{analysis['analysis_id']}/feedback"
        self.client.patch("/v1/users/me", json={"improvement_opt_in": True}, headers=self.headers)
        self.assertTrue(self.client.put(path, json={"rating": "helpful", "comment": "Clear explanation"}, headers=self.headers).json()["consented"])
        updated = self.client.put(path, json={"rating": "not_helpful"}, headers=self.headers).json()
        self.assertEqual(updated["comment"], "Clear explanation")
        self.assertEqual(self.client.put(path, json={"action_id": "invented", "rating": "helpful"}, headers=self.headers).status_code, 422)
        self.client.patch("/v1/users/me", json={"improvement_opt_in": False}, headers=self.headers)
        detail = self.client.get(f"/v1/analyses/{analysis['analysis_id']}", headers=self.headers).json()
        self.assertFalse(detail["feedback"][0]["consented"])
        stale_user = lambda: {"id": UUID(self.session["user_id"]), "improvement_opt_in": True}
        with patch.dict(app.dependency_overrides, {current_user: stale_user}):
            saved = self.client.put(path, json={"rating": "helpful"}, headers=self.headers).json()
        self.assertFalse(saved["consented"])
        self.assertEqual(len(self.client.get("/v1/users/me/export", headers=self.headers).json()["analyses"]), 1)
        self.assertEqual(self.client.delete("/v1/users/me/data", headers=self.headers).status_code, 204)
        self.assertEqual(self.client.get("/v1/analyses", headers=self.headers).status_code, 401)
        with pool.connection() as conn:
            self.assertIsNone(conn.execute("SELECT id FROM analyses WHERE id = %s", (analysis["analysis_id"],)).fetchone())

    def test_interrupted_analysis_recovers_without_ai(self):
        analysis = self.submit()
        with pool.connection() as conn:
            conn.execute("UPDATE analyses SET status = 'processing', explanation = NULL, created_at = now() - interval '2 minutes' WHERE id = %s", (analysis["analysis_id"],))
        with patch("app.ai.explain", side_effect=AssertionError("Unexpected paid call")):
            response = self.client.post("/v1/analyses", json=self.payload, headers=self.headers).json()
        self.assertEqual(response["status"], "complete")
        self.assertEqual(response["ai_status"], "fallback")

    def test_scenarios_do_not_save_or_call_ai(self):
        with patch("app.ai.explain", side_effect=AssertionError("Unexpected paid call")):
            result = self.client.post("/v1/scenarios", json=self.payload["snapshot"], headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["saved"])
        self.assertEqual(self.client.get("/v1/analyses", headers=self.headers).json()["items"], [])

    def test_chat_retry_review_and_export(self):
        body = {"request_id": str(uuid4()), "message": "Here are my fictional monthly details."}
        result = chat.fallback(complete_draft(), "generated")
        result["answer"] = "Review your captured numbers before creating a plan."
        with patch("app.chat.respond", return_value=result) as provider:
            first = self.client.post("/v1/chat", json=body, headers=self.headers)
            self.assertEqual(first.status_code, 201, first.text)
            again = self.client.post("/v1/chat", json=body, headers=self.headers)
            self.assertEqual(again.status_code, 200)
            self.assertEqual(again.json(), first.json())
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(self.client.get("/v1/analyses", headers=self.headers).json()["items"], [])
        turns = self.client.get("/v1/chat", headers=self.headers).json()["items"]
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["snapshot"]["monthly_income"], "4200")
        exported = self.client.get("/v1/users/me/export", headers=self.headers).json()
        self.assertEqual(exported["chat_turns"][0]["id"], first.json()["id"])
        body["message"] = "Changed request"
        self.assertEqual(self.client.post("/v1/chat", json=body, headers=self.headers).status_code, 409)
        self.client.delete("/v1/users/me/data", headers=self.headers)
        with pool.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM chat_turns WHERE user_id = %s", (self.session["user_id"],)).fetchone()["n"], 0)

    def test_chat_ownership_and_immutable_plan(self):
        analysis = self.submit()
        body = {"request_id": str(uuid4()), "message": "Why is this my first step?", "analysis_id": analysis["analysis_id"]}
        with patch("app.chat.respond", return_value=chat.fallback(chat.Draft())) as provider:
            turn = self.client.post("/v1/chat", json=body, headers=self.headers).json()
        self.assertEqual(str(provider.call_args.args[3]["analysis_id"]), analysis["analysis_id"])
        self.assertEqual(self.client.get(f"/v1/analyses/{analysis['analysis_id']}", headers=self.headers).json(), analysis)
        other = self.client.post("/v1/sessions").json()
        headers = {"Authorization": f"Bearer {other['token']}"}
        try:
            self.assertEqual(self.client.get(f"/v1/chat/{turn['id']}", headers=headers).status_code, 404)
            self.assertEqual(self.client.get("/v1/chat", headers=headers).json()["items"], [])
            self.assertEqual(self.client.post("/v1/chat", json=body, headers=headers).status_code, 404)
            self.assertEqual(self.client.post("/v1/chat", json=body).status_code, 401)
            invalid = {"request_id": str(uuid4()), "message": "x" * 2001}
            self.assertEqual(self.client.post("/v1/chat", json=invalid, headers=self.headers).status_code, 422)
        finally:
            self.client.delete("/v1/users/me/data", headers=headers)

    def test_chat_pending_recovery_and_rate_limit(self):
        body = {"request_id": str(uuid4()), "message": "Help me start."}
        first = self.client.post("/v1/chat", json=body, headers=self.headers).json()
        with pool.connection() as conn:
            conn.execute("UPDATE chat_turns SET status = 'processing' WHERE id = %s", (first["id"],))
        with patch("app.chat.respond", side_effect=AssertionError("Unexpected paid retry")):
            self.assertEqual(self.client.post("/v1/chat", json=body, headers=self.headers).status_code, 202)
            self.assertEqual(self.client.post("/v1/chat", json={**body, "request_id": str(uuid4())}, headers=self.headers).status_code, 409)
            with pool.connection() as conn:
                conn.execute("UPDATE chat_turns SET created_at = now() - interval '2 minutes' WHERE id = %s", (first["id"],))
            recovered = self.client.get(f"/v1/chat/{first['id']}", headers=self.headers).json()
            self.assertEqual(recovered["status"], "complete")
            self.assertEqual(recovered["ai_status"], "fallback")
        for _ in range(6):
            self.assertEqual(self.client.post("/v1/chat", json={**body, "request_id": str(uuid4())}, headers=self.headers).status_code, 201)
        self.assertEqual(self.client.post("/v1/chat", json={**body, "request_id": str(uuid4())}, headers=self.headers).status_code, 429)


if __name__ == "__main__":
    unittest.main()
