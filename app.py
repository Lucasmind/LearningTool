"""
Learning Tool — FastAPI entry point.
Local knowledge exploration tool with node-graph UI.
Serves API + static files on port 8100.
"""

import argparse
import asyncio
import json
import os
import uuid
import time
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse

from models import (
    QueryRequest, QueryResponse, JobStatusResponse,
    SessionCreate, SessionRename, SessionSummary, SessionFull,
    SessionSaveRequest, ProviderCreate, ProviderUpdate, DefaultProviderSet,
)
from llm_bridge import ProviderRegistry
from prompt_engineer import build_prompt, build_lineage_context
from session_manager import SessionManager
from settings_manager import SettingsManager

# ---- Paths ----
BASE_DIR = Path(__file__).parent.resolve()
STATIC_DIR = BASE_DIR / "static"
SESSIONS_DIR = BASE_DIR / "learning_sessions"
SETTINGS_DIR = BASE_DIR / "settings"

# ---- Parse CLI args (before FastAPI setup) ----
_parser = argparse.ArgumentParser(description="Learning Tool server")
_parser.add_argument("--port", type=int, default=8100, help="Server port (default: 8100)")
_parser.add_argument("--llm-url",
                      default=os.environ.get("LLM_URL", "http://localhost:11434/v1/chat/completions"),
                      help="LLM API endpoint (or set LLM_URL env var)")
_parser.add_argument("--llm-model", default="",
                      help="Model name (optional, server uses loaded model)")
_cli_args, _ = _parser.parse_known_args()

# ---- Shared state ----
settings_mgr = SettingsManager(SETTINGS_DIR, cli_url=_cli_args.llm_url, cli_model=_cli_args.llm_model)
provider_registry = ProviderRegistry(settings_mgr)
session_mgr = SessionManager(SESSIONS_DIR)

# Track running jobs: job_id -> dict
jobs: dict[str, dict] = {}


def _get_provider(provider_id: str | None = None):
    """Get provider by ID or return default."""
    if provider_id:
        try:
            return provider_registry.get(provider_id)
        except ValueError:
            pass
    return provider_registry.get_default()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    # Clean up expired trash on startup
    purged = session_mgr.cleanup_trash()
    if purged:
        print(f"Trash cleanup: permanently removed {purged} expired session(s)")
    yield


app = FastAPI(title="Learning Tool", lifespan=lifespan)


# ---- API: Query endpoints ----

@app.post("/api/query", response_model=QueryResponse)
async def submit_query(req: QueryRequest):
    """Submit a prompt (initial or follow-up). Returns job_id immediately."""
    job_id = f"job_{uuid.uuid4().hex[:12]}"

    # Load session to build lineage context if needed
    session_data = None
    if req.session_id:
        session_data = session_mgr.load(req.session_id)

    # Build the engineered prompt
    engineered = build_prompt(
        mode=req.mode,
        prompt_text=req.prompt_text,
        highlighted_text=req.highlighted_text,
        user_question=req.user_question,
        session_data=session_data,
        parent_node_id=req.parent_node_id,
    )

    # Record job
    jobs[job_id] = {
        "status": "queued",
        "engineered_prompt": engineered,
        "start_time": time.time(),
        "result": None,
        "error": None,
        "original_request": req.dict(),
        "provider_id": req.provider_id,
    }

    # Fire and forget — the queue serializes execution
    asyncio.ensure_future(_run_job(job_id, engineered, req.provider_id))

    return QueryResponse(
        job_id=job_id,
        status="queued",
        engineered_prompt=engineered,
    )


async def _run_job(job_id: str, prompt: str, provider_id: str | None = None):
    """Background task: run LLM query and store result."""
    job = jobs[job_id]
    provider = _get_provider(provider_id)
    try:
        job["status"] = "running"
        result = await provider.submit(prompt)
        job["status"] = "complete"
        job["result"] = result
    except Exception as e:
        # Try fallback
        fallback = provider_registry.get_fallback()
        if fallback and fallback.provider_id != provider.provider_id:
            try:
                result = await fallback.submit(prompt)
                job["status"] = "complete"
                job["result"] = result
                return
            except Exception:
                pass
        job["status"] = "error"
        job["error"] = str(e)


@app.get("/api/query/{job_id}/status", response_model=JobStatusResponse)
async def query_status(job_id: str):
    """Poll job status."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    job = jobs[job_id]
    elapsed = time.time() - job["start_time"]
    resp = JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        elapsed_seconds=round(elapsed, 1),
    )
    if job["status"] == "complete" and job["result"]:
        resp.response_html = job["result"].get("html", "")
        resp.response_text = job["result"].get("text", "")
    if job["status"] == "error":
        resp.error_message = job["error"]
    return resp


@app.post("/api/query/{job_id}/retry", response_model=QueryResponse)
async def retry_query(job_id: str):
    """Re-run the same prompt. Returns a new job_id."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    old = jobs[job_id]
    prompt = old["engineered_prompt"]
    provider_id = old.get("provider_id")
    new_job_id = f"job_{uuid.uuid4().hex[:12]}"
    jobs[new_job_id] = {
        "status": "queued",
        "engineered_prompt": prompt,
        "start_time": time.time(),
        "result": None,
        "error": None,
        "original_request": old["original_request"],
        "provider_id": provider_id,
    }
    asyncio.ensure_future(_run_job(new_job_id, prompt, provider_id))
    return QueryResponse(job_id=new_job_id, status="queued", engineered_prompt=prompt)


# ---- API: Streaming query endpoint ----

@app.post("/api/query/stream")
async def stream_query(req: QueryRequest):
    """Stream LLM response via Server-Sent Events.

    Events: prompt, thinking, token, done, error, fallback
    """
    session_data = None
    if req.session_id:
        session_data = session_mgr.load(req.session_id)

    engineered = build_prompt(
        mode=req.mode,
        prompt_text=req.prompt_text,
        highlighted_text=req.highlighted_text,
        user_question=req.user_question,
        session_data=session_data,
        parent_node_id=req.parent_node_id,
    )

    provider = _get_provider(req.provider_id)

    async def event_stream():
        # Send engineered prompt first so frontend can store it
        yield f"event: prompt\ndata: {json.dumps({'engineered_prompt': engineered})}\n\n"

        try:
            async for event_type, data in provider.stream(engineered):
                if event_type == "thinking":
                    yield f"event: thinking\ndata: {{}}\n\n"
                elif event_type == "token":
                    yield f"event: token\ndata: {json.dumps({'text': data})}\n\n"
                elif event_type == "done":
                    yield f"event: done\ndata: {json.dumps({'text': data})}\n\n"
                elif event_type == "error":
                    # Try fallback on error
                    fallback = provider_registry.get_fallback()
                    if fallback and fallback.provider_id != provider.provider_id:
                        yield f"event: fallback\ndata: {json.dumps({'from': provider.provider_id, 'to': fallback.provider_id})}\n\n"
                        async for fb_type, fb_data in fallback.stream(engineered):
                            if fb_type == "thinking":
                                yield f"event: thinking\ndata: {{}}\n\n"
                            elif fb_type == "token":
                                yield f"event: token\ndata: {json.dumps({'text': fb_data})}\n\n"
                            elif fb_type == "done":
                                yield f"event: done\ndata: {json.dumps({'text': fb_data})}\n\n"
                            elif fb_type == "error":
                                yield f"event: error\ndata: {json.dumps({'error': fb_data})}\n\n"
                        return
                    yield f"event: error\ndata: {json.dumps({'error': data})}\n\n"
        except Exception as e:
            # Try fallback on exception
            fallback = provider_registry.get_fallback()
            if fallback and fallback.provider_id != provider.provider_id:
                yield f"event: fallback\ndata: {json.dumps({'from': provider.provider_id, 'to': fallback.provider_id})}\n\n"
                try:
                    async for fb_type, fb_data in fallback.stream(engineered):
                        if fb_type == "thinking":
                            yield f"event: thinking\ndata: {{}}\n\n"
                        elif fb_type == "token":
                            yield f"event: token\ndata: {json.dumps({'text': fb_data})}\n\n"
                        elif fb_type == "done":
                            yield f"event: done\ndata: {json.dumps({'text': fb_data})}\n\n"
                        elif fb_type == "error":
                            yield f"event: error\ndata: {json.dumps({'error': fb_data})}\n\n"
                except Exception as fb_e:
                    yield f"event: error\ndata: {json.dumps({'error': str(fb_e)})}\n\n"
                return
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---- API: Title generation (uses default provider) ----

@app.post("/api/generate-title")
async def generate_title(req: QueryRequest):
    """Generate a short session title from the first prompt via LLM."""
    try:
        provider = provider_registry.get_default()
        result = await provider.submit(
            f'Generate a short title (max 6 words, no quotes, no punctuation at the end) '
            f'for a research session about this question:\n"{req.prompt_text}"\n'
            f'Reply with ONLY the title, nothing else.',
            timeout=30,
        )
        title = result.get("text", "").strip().strip('"\'').strip()
        # Take first line only, limit length
        title = title.split('\n')[0][:60]
        if not title:
            title = "Untitled Session"
        return {"title": title}
    except Exception as e:
        return {"title": "Untitled Session", "error": str(e)}


# ---- API: Settings endpoints ----

@app.get("/api/settings/providers")
async def list_providers():
    """List all providers with masked API keys."""
    providers = settings_mgr.get_all_providers()
    return {
        "providers": providers,
        "default_provider_id": settings_mgr.get_default_id(),
        "fallback_provider_id": settings_mgr.get_fallback_id(),
    }


@app.get("/api/settings/provider-list")
async def provider_list():
    """Lightweight provider list for dropdown."""
    return {
        "providers": settings_mgr.get_provider_list(),
        "default_provider_id": settings_mgr.get_default_id(),
    }


@app.post("/api/settings/providers")
async def add_provider(req: ProviderCreate):
    """Add a new LLM provider."""
    provider = settings_mgr.add_provider(req.dict())
    provider_registry.refresh()
    return provider


@app.put("/api/settings/providers/{provider_id}")
async def update_provider(provider_id: str, req: ProviderUpdate):
    """Update an existing provider."""
    updates = {k: v for k, v in req.dict().items() if v is not None}
    result = settings_mgr.update_provider(provider_id, updates)
    if not result:
        raise HTTPException(404, "Provider not found")
    provider_registry.refresh()
    return result


@app.delete("/api/settings/providers/{provider_id}")
async def delete_provider(provider_id: str):
    """Delete a provider."""
    ok = settings_mgr.delete_provider(provider_id)
    if not ok:
        raise HTTPException(400, "Cannot delete provider (not found or last remaining)")
    provider_registry.refresh()
    return {"status": "deleted"}


@app.post("/api/settings/providers/{provider_id}/test")
async def test_provider(provider_id: str):
    """Test connectivity to a provider."""
    raw = settings_mgr.get_provider_raw(provider_id)
    if not raw:
        raise HTTPException(404, "Provider not found")

    # Create a temporary provider instance for testing
    from llm_bridge import ProviderRegistry as PR
    temp_provider = PR._create(raw)
    result = await temp_provider.test()
    return result


@app.put("/api/settings/default-provider")
async def set_default_provider(req: DefaultProviderSet):
    """Set the default provider."""
    if not settings_mgr.set_default(req.provider_id):
        raise HTTPException(400, "Provider not found")
    return {"status": "ok", "default_provider_id": req.provider_id}


@app.put("/api/settings/fallback-provider")
async def set_fallback_provider(req: DefaultProviderSet):
    """Set the fallback provider (or None to clear)."""
    if not settings_mgr.set_fallback(req.provider_id):
        raise HTTPException(400, "Provider not found")
    return {"status": "ok", "fallback_provider_id": req.provider_id}


# ---- API: Ollama ----

@app.get("/api/ollama/models")
async def list_ollama_models(url: str = "http://localhost:11434"):
    """List models available on an Ollama instance."""
    import urllib.request
    import urllib.error
    tags_url = url.rstrip("/") + "/api/tags"
    try:
        req = urllib.request.Request(tags_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = []
            for m in data.get("models", []):
                models.append({
                    "name": m["name"],
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                })
            return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


# ---- API: Session endpoints ----

@app.get("/api/sessions", response_model=list[SessionSummary])
async def list_sessions():
    return session_mgr.list_all()


@app.post("/api/sessions", response_model=SessionSummary)
async def create_session(req: SessionCreate):
    return session_mgr.create(req.name)


@app.get("/api/sessions/{session_id}", response_model=SessionFull)
async def get_session(session_id: str):
    data = session_mgr.load(session_id)
    if not data:
        raise HTTPException(404, "Session not found")
    return data


@app.api_route("/api/sessions/{session_id}", methods=["PUT", "POST"])
async def save_session(session_id: str, req: SessionSaveRequest):
    session_mgr.save(session_id, req.dict())
    return {"status": "saved"}


@app.put("/api/sessions/{session_id}/rename")
async def rename_session(session_id: str, req: SessionRename):
    session_mgr.rename(session_id, req.name)
    return {"status": "renamed"}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    session_mgr.delete(session_id)
    return {"status": "deleted"}


# ---- API: Trash endpoints ----

@app.get("/api/trash")
async def list_trash():
    return session_mgr.list_trash()


@app.post("/api/trash/{session_id}/restore")
async def restore_session(session_id: str):
    ok = session_mgr.restore(session_id)
    if not ok:
        raise HTTPException(404, "Session not found in trash or restore conflict")
    return {"status": "restored"}


@app.delete("/api/trash/{session_id}")
async def permanent_delete_session(session_id: str):
    session_mgr.permanent_delete(session_id)
    return {"status": "permanently_deleted"}


# ---- Static files (must be last) ----

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    port = _cli_args.port
    print(f"Learning Tool starting at http://localhost:{port}")
    default_prov = settings_mgr.get_provider(settings_mgr.get_default_id())
    if default_prov:
        print(f"Default provider: {default_prov['alias']} ({default_prov['type']})")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
