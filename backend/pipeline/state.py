from typing import TypedDict, Optional

class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────
    run_id:          str
    issue_url:       str
    issue_title:     str
    issue_body:      str
    issue_comments:  list[str]
    issue_images:    list[str]
    repo_owner:      str
    repo_name:       str

    # ── Memory retrieval output ────────────────────────────
    memory_lessons:  list[str]
    memory_matches:  list[dict]

    # ── Code Reader output ─────────────────────────────────
    relevant_files:  list[dict]   # [{path: str, content: str}]

    # ── Planner output ─────────────────────────────────────
    plan:            str

    # ── Code Writer output ────────────────────────────────────────────────────
    file_changes:    list[dict]   # [{path: str, content: str}]
    retry_strategy:  str

    # ── Sandbox output ────────────────────────────────────
    sandbox_result:  dict

    # ── Critic output ─────────────────────────────────────
    critic_scores:   dict
    retry_count:     int
    memory_attempt_used: bool

    # ── Final output ──────────────────────────────────────
    pr_url:          Optional[str]
    status:          str          # "running" | "success" | "failed"
    error:           Optional[str]
