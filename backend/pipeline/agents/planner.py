import os
from google import genai
from pipeline.state import AgentState

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


async def planner(state: AgentState) -> dict:
    """
    Agent 2 — Planner
    Input state keys used:  issue_title, issue_body, relevant_files
    Output key returned:    plan (str)
    """
    # Concatenate all file contents into one readable block
    files_text = "\n\n".join(
        f"=== {f['path']} ===\n{f['content']}"
        for f in state["relevant_files"]
    )

    comments_text = "\n".join(f"- {c}" for c in state.get("issue_comments", []))

    prompt = f"""You are an expert software engineer fixing a GitHub issue.

Issue title: {state['issue_title']}
Issue body:  {state['issue_body']}
{f"Issue comments:{chr(10)}{comments_text}" if comments_text else ""}

Relevant source files:
{files_text}

Write a numbered step-by-step plan to fix this issue.
Be specific: name the file and function to change in each step.
Return plain text only — no JSON, no markdown headers."""

    resp = await _client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    plan = resp.text.strip()
    return {"plan": plan}