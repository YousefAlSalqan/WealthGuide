import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import ai, chat, settings
from .engine import SOURCES, build_plan
from .models import AnalysisRequest, ChatRequest, FeedbackRequest, Preferences, Snapshot

pool = ConnectionPool(settings.DATABASE_URL, min_size=1, max_size=5, open=False, kwargs={"row_factory": dict_row})
bearer = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app):
    pool.open()
    pool.wait(timeout=30)
    with pool.connection() as conn:
        conn.execute(Path(__file__).resolve().parents[1].joinpath("schema.sql").read_text())
    yield
    pool.close()


app = FastAPI(title="WealthGuide API", version="1.1.0", lifespan=lifespan,
              description="Local educational demo. Start a session, POST a snapshot, and receive a saved plan with an AI explanation.")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "api", "testserver"])


@app.middleware("http")
async def headers_and_limits(request: Request, call_next):
    # This local-only demo is same-origin. Reject foreign browser writes before they reach the API.
    origin = request.headers.get("origin")
    if origin and origin not in {"http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"}:
        return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()
        if len(body) > 32_768:
            return JSONResponse({"detail": "Request is too large"}, status_code=413)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # FastAPI's default includes the rejected input; return field paths/messages only.
    return JSONResponse(status_code=422, content={"detail": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]})


@app.exception_handler(psycopg.Error)
async def database_error(request, exc):
    return JSONResponse(status_code=503, content={"detail": "The database is temporarily unavailable. Retry the same request."})


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, "Start an anonymous demo session first.")
    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    with pool.connection() as conn:
        user = conn.execute("SELECT id, improvement_opt_in FROM users WHERE token_hash = %s", (token_hash,)).fetchone()
    if not user:
        raise HTTPException(401, "This session is no longer available. Start a new demo session.")
    return user


@app.get("/health")
def health():
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "mode": "local-demo", "ai_configured": bool(settings.get_api_key()) and settings.AI_ENABLED}


@app.post("/v1/sessions", status_code=201)
def create_session():
    user_id, token = uuid4(), secrets.token_urlsafe(32)
    with pool.connection() as conn:
        conn.execute("INSERT INTO users (id, token_hash) VALUES (%s, %s)", (user_id, hashlib.sha256(token.encode()).hexdigest()))
    return {"user_id": user_id, "token": token, "improvement_opt_in": False}


@app.get("/v1/users/me")
def me(user=Depends(current_user)):
    return {"user_id": user["id"], "improvement_opt_in": user["improvement_opt_in"]}


@app.patch("/v1/users/me")
def preferences(body: Preferences, user=Depends(current_user)):
    with pool.connection() as conn:
        conn.execute("UPDATE users SET improvement_opt_in = %s WHERE id = %s", (body.improvement_opt_in, user["id"]))
        if not body.improvement_opt_in:
            conn.execute("UPDATE feedback SET consented = FALSE WHERE analysis_id IN (SELECT a.id FROM analyses a JOIN financial_snapshots s ON s.id = a.snapshot_id WHERE s.user_id = %s)", (user["id"],))
    return {"user_id": user["id"], "improvement_opt_in": body.improvement_opt_in}


def owned_analysis(analysis_id: UUID, user_id: UUID) -> dict:
    with pool.connection() as conn:
        row = conn.execute("""SELECT a.*, s.data AS snapshot, s.user_id, s.request_id
            FROM analyses a JOIN financial_snapshots s ON s.id = a.snapshot_id
            WHERE a.id = %s AND s.user_id = %s""", (analysis_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, "Analysis not found.")
        # Recover an interrupted process without a second paid call or a background worker.
        if row["status"] == "processing" and row["created_at"] < datetime.now(timezone.utc) - timedelta(seconds=90):
            row["explanation"], row["status"], row["ai_status"] = ai.fallback(row["plan"]), "complete", "fallback"
            conn.execute("UPDATE analyses SET explanation = %s, status = 'complete', ai_status = 'fallback' WHERE id = %s AND status = 'processing'", (Jsonb(row["explanation"]), analysis_id))
        feedback = conn.execute("SELECT action_id, rating, action_status, comment, consented FROM feedback WHERE analysis_id = %s ORDER BY created_at", (analysis_id,)).fetchall()
    return {"analysis_id": row["id"], "user_id": row["user_id"], "request_id": row["request_id"],
            "snapshot": row["snapshot"], **row["plan"], "ai_explanation": row["explanation"],
            "status": row["status"], "ai_status": row["ai_status"], "model_version": row["model_version"],
            "prompt_version": row["prompt_version"], "created_at": row["created_at"], "feedback": feedback}


@app.post("/v1/analyses", status_code=201)
def analyze(body: AnalysisRequest, response: Response, user=Depends(current_user)):
    if body.user_id != user["id"]:
        raise HTTPException(403, "The submitted user ID does not belong to this session.")
    data = body.snapshot.model_dump(mode="json")
    plan = build_plan(body.snapshot)
    snapshot_id, analysis_id = uuid4(), uuid4()
    with pool.connection() as conn:
        # Lock only this user's short insert transaction, never the remote AI request.
        if not conn.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user["id"],)).fetchone():
            raise HTTPException(401, "Session deleted.")
        old = conn.execute("""SELECT a.id, s.data FROM financial_snapshots s
            JOIN analyses a ON a.snapshot_id = s.id WHERE s.user_id = %s AND s.request_id = %s""", (user["id"], body.request_id)).fetchone()
        if old:
            if old["data"] != data:
                raise HTTPException(409, "This request ID already belongs to a different snapshot.")
            analysis_id = old["id"]
        else:
            recent = conn.execute("SELECT count(*) AS n FROM financial_snapshots WHERE user_id = %s AND created_at > now() - interval '1 minute'", (user["id"],)).fetchone()["n"]
            if recent >= 5:
                raise HTTPException(429, "Please wait a minute before creating another plan.")
            conn.execute("INSERT INTO financial_snapshots (id, user_id, request_id, data, schema_version) VALUES (%s, %s, %s, %s, '1.0.0')", (snapshot_id, user["id"], body.request_id, Jsonb(data)))
            conn.execute("INSERT INTO analyses (id, snapshot_id, plan, status, ai_status, prompt_version) VALUES (%s, %s, %s, 'processing', 'pending', %s)", (analysis_id, snapshot_id, Jsonb(plan), ai.PROMPT_VERSION))
    if not old:
        explanation, ai_status, model = ai.explain(plan)
        with pool.connection() as conn:
            conn.execute("UPDATE analyses SET explanation = %s, status = 'complete', ai_status = %s, model_version = %s WHERE id = %s AND status = 'processing'", (Jsonb(explanation), ai_status, model, analysis_id))
    result = owned_analysis(analysis_id, user["id"])
    if old:
        response.status_code = 202 if result["status"] == "processing" else 200
    return result


@app.get("/v1/analyses")
def history(limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0), user=Depends(current_user)):
    with pool.connection() as conn:
        rows = conn.execute("""SELECT a.id AS analysis_id, a.created_at, a.status, a.ai_status,
            a.plan->'metrics' AS metrics, s.data->>'as_of' AS as_of,
            a.plan->'actions'->0->>'title' AS top_action
            FROM analyses a JOIN financial_snapshots s ON s.id = a.snapshot_id
            WHERE s.user_id = %s ORDER BY a.created_at DESC, a.id DESC LIMIT %s OFFSET %s""", (user["id"], limit + 1, offset)).fetchall()
    return {"items": rows[:limit], "has_more": len(rows) > limit}


@app.get("/v1/analyses/{analysis_id}")
def detail(analysis_id: UUID, user=Depends(current_user)):
    return owned_analysis(analysis_id, user["id"])


@app.post("/v1/scenarios")
def scenario(snapshot: Snapshot, user=Depends(current_user)):
    return {**build_plan(snapshot), "saved": False}


@app.put("/v1/analyses/{analysis_id}/feedback")
def feedback(analysis_id: UUID, body: FeedbackRequest, user=Depends(current_user)):
    analysis = owned_analysis(analysis_id, user["id"])
    if body.action_id not in {"overview", *(a["id"] for a in analysis["actions"])}:
        raise HTTPException(422, "This action does not belong to the analysis.")
    with pool.connection() as conn:
        # Serialize with preference changes so an in-flight request cannot undo opt-out.
        preference = conn.execute("SELECT improvement_opt_in FROM users WHERE id = %s FOR UPDATE", (user["id"],)).fetchone()
        if not preference:
            raise HTTPException(401, "Session deleted.")
        row = conn.execute("""INSERT INTO feedback (id, analysis_id, action_id, rating, action_status, comment, consented)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (analysis_id, action_id) DO UPDATE SET
                rating = COALESCE(EXCLUDED.rating, feedback.rating),
                action_status = COALESCE(EXCLUDED.action_status, feedback.action_status),
                comment = COALESCE(%s, feedback.comment), consented = EXCLUDED.consented, updated_at = now()
            RETURNING action_id, rating, action_status, comment, consented""",
            (uuid4(), analysis_id, body.action_id, body.rating, body.action_status, body.comment or "", preference["improvement_opt_in"], body.comment)).fetchone()
    return row


@app.get("/v1/guidance")
def guidance():
    return SOURCES


@app.get("/v1/users/me/export")
def export_data(user=Depends(current_user)):
    with pool.connection() as conn:
        rows = conn.execute("SELECT a.id FROM analyses a JOIN financial_snapshots s ON s.id = a.snapshot_id WHERE s.user_id = %s ORDER BY a.created_at", (user["id"],)).fetchall()
        turns = conn.execute("SELECT * FROM chat_turns WHERE user_id = %s ORDER BY created_at, id", (user["id"],)).fetchall()
    return JSONResponse(jsonable_encoder({"user_id": user["id"], "analyses": [owned_analysis(r["id"], user["id"]) for r in rows],
                                         "chat_turns": [public_chat(t) for t in turns]}), headers={"Content-Disposition": 'attachment; filename="wealthguide-export.json"'})


@app.delete("/v1/users/me/data", status_code=204)
def delete_data(user=Depends(current_user)):
    with pool.connection() as conn:
        conn.execute("DELETE FROM users WHERE id = %s", (user["id"],))
    return Response(status_code=204)


def public_chat(row):
    return {k: row[k] for k in ("id", "request_id", "message", "analysis_id", "status", "created_at")} | row["result"]


def recover_chat(conn, user_id):
    conn.execute("""UPDATE chat_turns SET status = 'complete',
        result = jsonb_set(jsonb_set(result, '{ai_status}', '"fallback"'), '{answer}', to_jsonb(%s::text))
        WHERE user_id = %s AND status = 'processing' AND created_at < now() - interval '90 seconds'""",
        ("This reply was interrupted. Your earlier draft is safe. Send a new message or use the snapshot form.", user_id))


@app.get("/v1/chat")
def chat_history(user=Depends(current_user)):
    with pool.connection() as conn:
        recover_chat(conn, user["id"])
        rows = conn.execute("SELECT * FROM chat_turns WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT 21", (user["id"],)).fetchall()
    return {"items": [public_chat(r) for r in reversed(rows[:20])], "has_more": len(rows) > 20}


@app.get("/v1/chat/{turn_id}")
def chat_detail(turn_id: UUID, user=Depends(current_user)):
    with pool.connection() as conn:
        recover_chat(conn, user["id"])
        row = conn.execute("SELECT * FROM chat_turns WHERE id = %s AND user_id = %s", (turn_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Chat message not found.")
    return public_chat(row)


@app.post("/v1/chat", status_code=201)
def chat_message(body: ChatRequest, response: Response, user=Depends(current_user)):
    plan = owned_analysis(body.analysis_id, user["id"]) if body.analysis_id else None
    turn_id = uuid4()
    with pool.connection() as conn:
        if not conn.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user["id"],)).fetchone():
            raise HTTPException(401, "Session deleted.")
        recover_chat(conn, user["id"])
        old = conn.execute("SELECT * FROM chat_turns WHERE user_id = %s AND request_id = %s", (user["id"], body.request_id)).fetchone()
        if old:
            if old["message"] != body.message or old["analysis_id"] != body.analysis_id:
                raise HTTPException(409, "This request ID belongs to a different chat message.")
            response.status_code = 202 if old["status"] == "processing" else 200
            return public_chat(old)
        if conn.execute("SELECT id FROM chat_turns WHERE user_id = %s AND status = 'processing'", (user["id"],)).fetchone():
            raise HTTPException(409, "A reply is still being prepared. Wait for it before sending another message.")
        recent = conn.execute("SELECT count(*) AS n FROM chat_turns WHERE user_id = %s AND created_at > now() - interval '1 minute'", (user["id"],)).fetchone()["n"]
        if recent >= 6:
            raise HTTPException(429, "Please wait a minute before sending another chat message.")
        history = list(reversed(conn.execute("SELECT * FROM chat_turns WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT 6", (user["id"],)).fetchall()))
        previous = chat.Draft.model_validate(history[-1]["result"]["draft"]) if history else chat.Draft()
        conn.execute("""INSERT INTO chat_turns (id, user_id, request_id, message, analysis_id, result, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'processing')""",
            (turn_id, user["id"], body.request_id, body.message, body.analysis_id, Jsonb(chat.fallback(previous, "pending"))))
    result = chat.respond(body.message, previous, history, plan)
    with pool.connection() as conn:
        conn.execute("UPDATE chat_turns SET result = %s, status = 'complete' WHERE id = %s AND status = 'processing'", (Jsonb(result), turn_id))
    return chat_detail(turn_id, user)
