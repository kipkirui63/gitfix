import os
import json
import base64
import httpx
from google import genai
from pipeline.state import AgentState

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


async def code_reader(state: AgentState) -> dict:
    """
    Agent 1 — Code Reader
    Input state keys used:  repo_owner, repo_name, issue_title, issue_body
    Output key returned:    relevant_files [{path, content}]
    """
    headers = {"Authorization": f"token {os.environ['GITHUB_TOKEN']}"}

    # ── Step 1: Get the full file tree of the repo ──────────────────────────────
    # ?recursive=1 returns ALL nested files in one request (no pagination needed)
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            f"https://api.github.com/repos/{state['repo_owner']}/{state['repo_name']}"
            f"/git/trees/HEAD?recursive=1",
            headers=headers,
        )
        result = resp.json()

    # Keep only source files; skip binaries/dotfiles/huge files
    paths = []

    for item in result.get("tree", []):
        # check all 3 conditions
        if item["type"] == "blob":
            if not item["path"].startswith("."):
                if item.get("size", 0) < 80_000:
                    paths.append(item["path"])

    # ── Step 2: Ask Groq which files are most relevant ──────────────────────────
    # response_format=json_object forces Groq to return valid JSON (no prose)
    comments_text = "\n".join(f"- {c}" for c in state.get("issue_comments", []))

    prompt = f"""Issue title: {state['issue_title']}
                Issue body: {state['issue_body']}
                {f"Issue comments:{chr(10)}{comments_text}" if comments_text else ""}

                Files in the repo:
                {chr(10).join(paths)}

                Return a JSON object with a "files" key listing the 5 most relevant file paths.
                Example: {{"files": ["src/foo.py", "lib/bar.py"]}}"""

    gemini_resp = await _client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    raw = gemini_resp.text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        end = -1 if lines[-1].startswith("```") else len(lines)
        raw = "\n".join(lines[1:end])
    picked = json.loads(raw)
    # Groq might return {"files": [...]} or {"paths": [...]} — grab the first list value
    if isinstance(picked, dict):
        picked = next(iter(picked.values()))

    # ── Step 3: Download the content of each selected file ──────────────────────
    # GitHub returns file content base64-encoded inside the JSON response
    relevant_files = []
    async with httpx.AsyncClient(timeout=20) as http:
        for path in picked[:5]:
            r = await http.get(
                f"https://api.github.com/repos/{state['repo_owner']}/{state['repo_name']}"
                f"/contents/{path}",
                headers=headers,
            )
            data = r.json()
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            relevant_files.append({"path": path, "content": content})

    return {"relevant_files": relevant_files}