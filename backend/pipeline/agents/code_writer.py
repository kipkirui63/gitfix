import os
import json
from google import genai
from pipeline.state import AgentState

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


async def code_writer(state: AgentState) -> dict:
    """
    Agent 3 — Code Writer
    Input state keys used:  issue_title, issue_body, relevant_files, plan
    Output key returned:    file_changes [{path, content}]
    """
    files_text = "\n\n".join(
        f"=== {f['path']} ===\n{f['content']}"
        for f in state["relevant_files"]
    )

    comments_text = "\n".join(f"- {c}" for c in state.get("issue_comments", []))

    paths_list = "\n".join(f['path'] for f in state["relevant_files"])

    prompt = f"""You are an expert software engineer fixing a GitHub issue.

Issue title: {state['issue_title']}
Issue body:  {state['issue_body']}
{f"Issue comments:{chr(10)}{comments_text}" if comments_text else ""}

Fix plan:
{state['plan']}

Current file contents:
{files_text}

Task: Apply the fix plan to the relevant files. For each file you modify, return its COMPLETE new content.

Return a JSON object with a "files" key containing a list of changed files:
{{
  "files": [
    {{
      "path": "path/to/file.py",
      "content": "...complete new file content..."
    }}
  ]
}}

Rules:
- Only include files that actually need to change.
- Return the FULL file content for each changed file, not just the changed lines.
- Do not include any explanation outside the JSON.
- Available file paths: {paths_list}"""

    response = await _client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        end = -1 if lines[-1].startswith("```") else len(lines)
        raw = "\n".join(lines[1:end])

    data = json.loads(raw)
    file_changes = data.get("files", [])

    return {"file_changes": file_changes}
