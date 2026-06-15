# TODO: Agent 4 — Sandbox (E2B)
# No LLM — uses E2B cloud containers
# Input:  patch, relevant_files
# Output: sandbox_result {tests_passed, test_output, security_issues, security_score}
# Steps:  spin up container → apply patch → run pytest → run bandit → destroy


import os
import json
import asyncio
from e2b import Sandbox
from pipeline.state import AgentState
from pipeline.events import push_event


async def sandbox(state: AgentState) -> dict:
    run_id = state.get("run_id", "")
    await push_event(run_id, {"agent": "sandbox", "status": "running", "msg": "Spinning up sandbox…"})

    result = await asyncio.to_thread(_run_in_sandbox, state) # run _run_in_sandbox in thread so that it doesn't block the event loop

    await push_event(run_id, {
        "agent": "sandbox",
        "status": "done",
        "tests_passed": result["tests_passed"],
        "security_score": round(result["security_score"], 2),
        "msg": "✅ Tests passed" if result["tests_passed"] else "❌ Tests failed",
    })
    return {"sandbox_result": result}


def _run_in_sandbox(state: dict) -> dict:
    file_changes  = state.get("file_changes", [])
    relevant_files = state.get("relevant_files", [])

    if not os.environ.get("E2B_API_KEY"):
        return {
            "tests_passed": True,
            "test_output": "Sandbox skipped — E2B_API_KEY not configured",
            "security_issues": [],
            "security_score": 0.8,
        }

    sbx = Sandbox.create(timeout=120)
    try:
        # Write original files first
        for f in relevant_files:
            dir_path = "/".join(f["path"].split("/")[:-1])
            if dir_path:
                sbx.commands.run(f"mkdir -p /code/{dir_path}")
            sbx.files.write(f"/code/{f['path']}", f["content"])

        # Overwrite with changed files
        for f in file_changes:
            dir_path = "/".join(f["path"].split("/")[:-1])
            if dir_path:
                sbx.commands.run(f"mkdir -p /code/{dir_path}")
            sbx.files.write(f"/code/{f['path']}", f["content"])

        # Detect all languages in the repo and collect test suites to run
        file_paths = [f["path"] for f in relevant_files]
        names = {p.split("/")[-1] for p in file_paths}
        suites = _detect_test_command(names, sbx) #returns list of test suites to run

        all_output = []
        tests_passed = True   # innocent until proven guilty

        for test_cmd, install_cmd, suite_is_python in suites:
            if install_cmd:
                try:
                    sbx.commands.run(install_cmd)
                except Exception:
                    pass

            try:
                test_r = sbx.commands.run(f"cd /code && {test_cmd} 2>&1")
                output = (test_r.stdout or "").strip()
                exit_code = test_r.exit_code
            except Exception as e:
                output = str(e)
                exit_code = 1
            all_output.append(f"$ {test_cmd}\n{output}")

            if suite_is_python:
                passed = exit_code in (0, 5)   # 5 = no tests collected
            else:
                passed = exit_code == 0

            if not passed:
                tests_passed = False   # any suite failing = overall fail

        test_output = "\n\n".join(all_output)
        issues, security_score = _run_security_scan(sbx, names)

        return {
            "tests_passed": tests_passed,
            "test_output": test_output[:2000],
            "security_issues": issues,
            "security_score": security_score,
        }
    finally:
        sbx.kill()


def _detect_test_command(names: set[str], sbx) -> list[tuple[str, str, bool]]:
    """
    Returns a list of (test_cmd, install_cmd, is_python) tuples.
    One tuple per language detected — supports fullstack repos with multiple languages.
    e.g. Python backend + JS frontend returns two tuples, both suites run.
    """
    suites = []

    # JavaScript / TypeScript
    if "package.json" in names:
        pkg = sbx.commands.run("cat /code/package.json 2>/dev/null")
        pkg_text = pkg.stdout or ""
        sbx.commands.run("cd /code && npm install -q 2>&1")
        if '"jest"' in pkg_text:
            suites.append(("npx jest --ci 2>&1", "", False))
        elif '"vitest"' in pkg_text:
            suites.append(("npx vitest run 2>&1", "", False))
        elif '"mocha"' in pkg_text:
            suites.append(("npx mocha 2>&1", "", False))
        else:
            suites.append(("npm test 2>&1", "", False))

    # Go
    if "go.mod" in names:
        suites.append(("go test ./... 2>&1", "", False))

    # Rust
    if "Cargo.toml" in names:
        suites.append(("cargo test 2>&1", "", False))

    # Java (Maven)
    if "pom.xml" in names:
        suites.append(("mvn test -q 2>&1", "", False))

    # Java (Gradle)
    if "build.gradle" in names or "build.gradle.kts" in names:
        suites.append(("./gradlew test 2>&1", "", False))

    # Ruby
    if "Gemfile" in names:
        suites.append(("bundle exec rspec 2>&1", "gem install bundler -q && bundle install -q", False))

    # Python — check for .py files anywhere in the repo
    if any(n.endswith(".py") for n in names):
        suites.append(("python -m pytest --tb=short -q 2>&1", "pip install pytest -q --disable-pip-version-check", True))

    # Nothing detected — default to pytest as a last resort
    if not suites:
        suites.append(("python -m pytest --tb=short -q 2>&1", "pip install pytest -q --disable-pip-version-check", True))

    return suites


def _run_security_scan(sbx, names: set[str]) -> tuple[list, float]:
    """
    Returns (all_issues, average_security_score).
    Runs every applicable scanner for all languages detected in the repo.
    For fullstack repos (e.g. Python backend + JS frontend + Rust service),
    all scanners run and their scores are averaged.
    """
    all_issues = []
    scores = []

    # Python — bandit
    if any(n.endswith(".py") for n in names):
        r = sbx.commands.run("cd /code && bandit -r . -f json -ll -q 2>&1")
        try:
            data = json.loads((r.stdout or "").strip())
            issues = data.get("results", [])
            high = sum(1 for i in issues if i.get("issue_severity") == "HIGH")
            med  = sum(1 for i in issues if i.get("issue_severity") == "MEDIUM")
            all_issues.extend(issues)
            scores.append(max(0.0, 1.0 - high * 0.3 - med * 0.1))
        except (json.JSONDecodeError, KeyError):
            scores.append(0.8)

    # JavaScript/TypeScript — eslint-plugin-security
    if "package.json" in names:
        sbx.commands.run("npm install -g eslint @microsoft/eslint-plugin-security --silent 2>&1")
        r = sbx.commands.run("cd /code && npx eslint . --format json 2>&1")
        try:
            data = json.loads((r.stdout or "").strip())
            issues = [m for f in data for m in f.get("messages", [])]
            high = sum(1 for i in issues if i.get("severity") == 2)  # 2 = error
            med  = sum(1 for i in issues if i.get("severity") == 1)  # 1 = warning
            all_issues.extend(issues)
            scores.append(max(0.0, 1.0 - high * 0.3 - med * 0.1))
        except (json.JSONDecodeError, KeyError):
            scores.append(0.8)

    # Go — gosec
    if "go.mod" in names:
        sbx.commands.run("go install github.com/securego/gosec/v2/cmd/gosec@latest 2>&1")
        r = sbx.commands.run("cd /code && gosec -fmt json ./... 2>&1")
        try:
            data = json.loads((r.stdout or "").strip())
            issues = data.get("Issues", [])
            high = sum(1 for i in issues if i.get("severity") == "HIGH")
            med  = sum(1 for i in issues if i.get("severity") == "MEDIUM")
            all_issues.extend(issues)
            scores.append(max(0.0, 1.0 - high * 0.3 - med * 0.1))
        except (json.JSONDecodeError, KeyError):
            scores.append(0.8)

    # Rust — cargo audit
    if "Cargo.toml" in names:
        r = sbx.commands.run("cd /code && cargo audit --json 2>&1")
        try:
            data = json.loads((r.stdout or "").strip())
            issues = data.get("vulnerabilities", {}).get("list", [])
            all_issues.extend(issues)
            scores.append(max(0.0, 1.0 - len(issues) * 0.3))
        except (json.JSONDecodeError, KeyError):
            scores.append(0.8)

    # Ruby — bundler-audit
    if "Gemfile" in names:
        sbx.commands.run("gem install bundler-audit -q 2>&1")
        r = sbx.commands.run("cd /code && bundle-audit check --format json 2>&1")
        try:
            data = json.loads((r.stdout or "").strip())
            issues = data.get("results", [])
            all_issues.extend(issues)
            scores.append(max(0.0, 1.0 - len(issues) * 0.2))
        except (json.JSONDecodeError, KeyError):
            scores.append(0.8)

    # No scanner matched (Java or unknown) — neutral
    if not scores:
        return [], 0.8

    # Average across all scanners that ran
    return all_issues, round(sum(scores) / len(scores), 3)