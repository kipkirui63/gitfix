import os
import re
import asyncio
from github import Github, GithubException
from pipeline.state import AgentState


async def pr_opener(state: AgentState) -> dict:
    """
    Agent 5 — PR Opener  (no LLM — uses GitHub API only)
    Input state keys used:  repo_owner, repo_name, issue_title, plan, file_changes
    Output key returned:    pr_url
    """
    g  = Github(os.environ["GITHUB_TOKEN"])
    me = g.get_user()

    # Get the upstream (original) repo object
    upstream = g.get_repo(f"{state['repo_owner']}/{state['repo_name']}")

    # Fork it. If you already have a fork, PyGithub returns the existing one.
    fork = me.create_fork(upstream)

    # Build a URL-safe branch name from the issue title
    slug = re.sub(r"[^a-z0-9-]", "-", state["issue_title"].lower()[:50])
    slug = re.sub(r"-+", "-", slug).strip("-")
    branch_name = f"gitfixr/{slug}"

    # Create the branch off the fork's default branch HEAD commit.
    # GitHub creates forks asynchronously — retry until the branch is ready.
    for attempt in range(10):
        try:
            default_sha = fork.get_branch(fork.default_branch).commit.sha
            break
        except GithubException:
            if attempt == 9:
                raise
            await asyncio.sleep(3)

    try:
        fork.create_git_ref(ref=f"refs/heads/{branch_name}", sha=default_sha)
    except GithubException:
        pass  # branch already exists from a previous attempt — reuse it

    # Commit each changed file directly to the branch
    for f in state.get("file_changes", []):
        path    = f["path"]
        content = f["content"]
        try:
            existing = fork.get_contents(path, ref=branch_name)
            fork.update_file(
                path    = path,
                message = f"gitfixr: fix {path}",
                content = content,
                sha     = existing.sha,
                branch  = branch_name,
            )
        except GithubException:
            fork.create_file(
                path    = path,
                message = f"gitfixr: fix {path}",
                content = content,
                branch  = branch_name,
            )

    # Open the PR: fork:branch → upstream:default_branch
    body = (
        "Automated fix by [gitFixr](https://github.com/laharigandrapu/gitfixr).\n\n"
        "**Fix plan:**\n" + state["plan"]
    )
    try:
        pr = upstream.create_pull(
            title = f"[gitfixr] Fix: {state['issue_title']}",
            body  = body,
            head  = f"{me.login}:{branch_name}",
            base  = upstream.default_branch,
        )
    except GithubException:
        # PR already exists — find and return it
        existing_prs = upstream.get_pulls(head=f"{me.login}:{branch_name}", state="open")
        pr = next(iter(existing_prs), None)
        if pr is None:
            raise

    return {"pr_url": pr.html_url}
