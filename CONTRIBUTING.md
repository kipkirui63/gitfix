# Contributing to gitFixr

This document outlines the phased build plan for gitFixr.

---

## Phase 1 — Foundation

**Goal:** Skeleton runs end-to-end with no real logic yet.

- Set up repo structure (`backend/`, `extension/` folders)
- Create `.env` from `.env.example` and obtain all API keys (Groq, Gemini, E2B, GitHub token)
- `backend/main.py` — FastAPI app, `POST /fix-issue` returns a `run_id`
- `backend/pipeline/state.py` — `AgentState` TypedDict
- `backend/database/db.py` + `models.py` — SQLite setup, create tables
- `extension/manifest.json` — Chrome extension config
- `extension/content_script.js` — detect GitHub issue URL, extract title and body
- `extension/background.js` — send issue URL to backend, receive `run_id`

---

## Phase 2 — Core Pipeline

**Goal:** Issue goes in → patch comes out (no retries yet).

- `pipeline/agents/code_reader.py` — Groq call to pick relevant files from the repo
- `pipeline/agents/planner.py` — Groq call to generate a fix plan
- `pipeline/agents/code_writer.py` — Gemini Flash call to write the unified diff
- `pipeline/graph.py` — wire agents 1–3 into a LangGraph `StateGraph`
- `pipeline/agents/pr_opener.py` — GitHub API: fork repo → create branch → commit patch → open PR
- `extension/sidebar.html` + `sidebar.js` — basic UI showing pipeline status and PR link
- `extension/content_script.js` — also extract issue comments from the page DOM and include them in the payload sent to the backend, so agents have full context (comments often contain the exact file/line or maintainer clarifications)
- `extension/content_script.js` + `pipeline/agents/code_writer.py` — extract image URLs from the issue body and pass them to Gemini Flash (which is multimodal) so screenshots attached to issues are included as visual context when generating the patch

---

## Phase 3 — Sandbox + Critic

**Goal:** Patch is tested before the PR is opened.

- `pipeline/agents/sandbox.py` — E2B container: apply patch, run `pytest` + `bandit`, return results
- `pipeline/agents/critic.py` — Groq scores quality / coverage / security; if overall < 0.8, increment `retry_count` and loop back to code_writer
- `backend/main.py` — add WebSocket route `WS /stream/{run_id}` to stream live events
- `extension/sidebar.js` — connect to WebSocket and display sandbox results and critic scores live

---

## Phase 4 — Self-Healing Memory

**Goal:** System learns from failures and improves over time.

- `pipeline/memory/retrieval.py` — embed issue with `sentence-transformers`, query ChromaDB for top 3 lessons
- `pipeline/memory/storage.py` — after all retries fail, store failure embedding + lesson in ChromaDB
- `pipeline/graph.py` — wire memory nodes (retrieval before `code_reader`, storage after critic gives up)

---

## Phase 5 — Dashboard + Polish

**Goal:** Stats are visible and the system feels complete.

- `backend/main.py` — implement `GET /dashboard/stats` endpoint
- `extension/dashboard.html` + `dashboard.js` — render success rate, per-agent reliability, learning curve
- Test on 5+ real GitHub issues and fix any failures
- Fill in the benchmark table in `README.md`

---

## Phase 6 — Ship

**Goal:** Live and publicly available.

- Deploy backend to Render.com (free tier)
- Update `BACKEND_URL` in the extension to the deployed URL
- Package extension for the Chrome Web Store
- Run on 25+ real issues and complete the benchmark table
