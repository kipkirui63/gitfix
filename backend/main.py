from dotenv import load_dotenv
load_dotenv()

import uuid
import asyncio
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

import json
from fastapi import WebSocket
from pipeline.events import create_run_queue, get_run_queue, push_event, remove_run_queue

from database.db import get_db, init_db, SessionLocal
from database.models import Run

app = FastAPI(title="gitFixr API")

# Allow Chrome extension to call the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ── Request / Response models ──────────────────────────────────────────────────

class FixIssueRequest(BaseModel):
    issue_url:      str
    issue_title:    str
    issue_body:     str
    issue_comments: list[str] = []
    issue_images:   list[str] = []

class FixIssueResponse(BaseModel):
    run_id: str
    status: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/fix-issue", response_model=FixIssueResponse)
async def fix_issue(payload: FixIssueRequest, db: Session = Depends(get_db)):
    run_id = str(uuid.uuid4())

    # Parse repo owner and name from the GitHub issue URL
    # URL format: https://github.com/{owner}/{repo}/issues/{number}
    parts = payload.issue_url.replace("https://github.com/", "").split("/")
    repo_owner = parts[0]
    repo_name  = parts[1]

    # Save the run as "running" immediately so the sidebar can poll it
    run = Run(
        run_id    = run_id,
        issue_url = payload.issue_url,
        status    = "running",
    )
    db.add(run)
    db.commit()

    # Build the initial pipeline state
    initial_state = {
        "run_id":             run_id,
        "issue_url":          payload.issue_url,
        "issue_title":        payload.issue_title,
        "issue_body":         payload.issue_body,
        "issue_comments":     payload.issue_comments,
        "issue_images":       payload.issue_images,
        "repo_owner":         repo_owner,
        "repo_name":          repo_name,
        "memory_lessons":     [],
        "memory_matches":     [],
        "relevant_files":     [],
        "plan":               "",
        "file_changes":       [],
        "retry_strategy":     "standard",
        "sandbox_result":     {},
        "critic_scores":      {},
        "retry_count":        0,
        "memory_attempt_used": False,
        "pr_url":             None,
        "status":             "running",
        "error":              None,
    }

    # Fire and forget — pipeline runs in background, HTTP response returns immediately
    asyncio.create_task(_run_pipeline(run_id, initial_state))

    return FixIssueResponse(run_id=run_id, status="running")


@app.get("/status/{run_id}")
def get_status(run_id: str, db: Session = Depends(get_db)):
    """Sidebar polls this every 3 seconds to check progress."""
    run = db.query(Run).filter(Run.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"status": run.status, "pr_url": run.pr_url, "error": run.error}


@app.websocket("/stream/{run_id}")
async def stream_run(ws: WebSocket, run_id: str):
    await ws.accept()
    q = get_run_queue(run_id) #get the queue for the run id
    if q is None:
        await ws.send_text(json.dumps({"error": "run not found or already finished"}))
        await ws.close()
        return
    try:
        while True: #iterate through the queue and send events to the frontend
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0) #wait for 30 seconds for an event to be pushed to the queue
                if event is None: #if the event is None, it means the pipeline has finished
                    break
                await ws.send_text(json.dumps(event)) #send the event to the frontend
            except asyncio.TimeoutError: #if no event is received in 30 seconds, send a ping to keep the connection alive
                await ws.send_text(json.dumps({"type": "ping"})) #send a ping to keep the connection alive
    except Exception:
        pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Background pipeline runner ─────────────────────────────────────────────────

async def _run_pipeline(run_id: str, state: dict):
    from pipeline.graph import build_graph

    create_run_queue(run_id)
    graph = build_graph()
    db = SessionLocal()
    try:
        result = await graph.ainvoke(state)
        db.query(Run).filter(Run.run_id == run_id).update({
            "status": "success",
            "pr_url": result.get("pr_url"),
        })
    except Exception as exc:
        db.query(Run).filter(Run.run_id == run_id).update({
            "status": "failed",
            "error": str(exc),
        })
        print(f"[gitFixr] Pipeline error for {run_id}: {exc}")
    finally:
        db.commit()
        db.close()
        await push_event(run_id, None)
        remove_run_queue(run_id)