const BACKEND_WS = "ws://localhost:8001";
const box      = document.getElementById("box");
const prLink   = document.getElementById("pr-link");
const prAnchor = document.getElementById("pr-anchor");
const details  = document.getElementById("details");
const fixBtn   = document.getElementById("fix-btn");

let ws = null;

chrome.storage.local.get(["status", "pr_url", "error", "run_id", "pending_issue"], (stored) => {
  if (stored.status) render(stored);
  if (stored.status === "running" && stored.run_id) {
    connectWebSocket(stored.run_id);
  }
  // Show button only if we're on an issue page and not already running
  if (stored.pending_issue && stored.status !== "running") {
    fixBtn.style.display = "block";
  }
});

fixBtn.addEventListener("click", () => {
  chrome.storage.local.get("pending_issue", ({ pending_issue }) => {
    if (!pending_issue) return;
    fixBtn.disabled = true;
    fixBtn.textContent = "Starting…";
    chrome.runtime.sendMessage({ type: "FIX_ISSUE", payload: pending_issue }, (response) => {
      if (response?.run_id) {
        fixBtn.style.display = "none";
        details.innerHTML = "";
        connectWebSocket(response.run_id);
      } else {
        fixBtn.disabled = false;
        fixBtn.textContent = "🔧 Fix this Issue";
      }
    });
  });
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "PIPELINE_UPDATE") render(msg.payload);
});

function connectWebSocket(run_id) {
  if (ws) return;
  ws = new WebSocket(`${BACKEND_WS}/stream/${run_id}`);
  ws.onmessage = (event) => {
    try { handleStreamEvent(JSON.parse(event.data)); } catch (_) {}
  };
  ws.onerror = () => { ws = null; };
  ws.onclose = () => { ws = null; };
}

function handleStreamEvent(data) {
  if (data.type === "ping") return;

  if (data.agent === "sandbox") {
    if (data.status === "running") {
      addDetail(`🔬 Sandbox: ${data.msg}`);
    } else if (data.status === "done") {
      const icon = data.tests_passed ? "✅" : "❌";
      addDetail(`${icon} Tests: ${data.tests_passed ? "passed" : "failed"} · Security: ${(data.security_score * 100).toFixed(0)}%`);
    }
  }

  if (data.agent === "critic") {
    if (data.status === "running") {
      addDetail("🤖 Critic: scoring patch…");
    } else if (data.status === "done") {
      const s = data.scores;
      addDetail(`📊 Quality ${pct(s.quality)} · Coverage ${pct(s.coverage)} · Security ${pct(s.security)} · Overall ${pct(s.overall)}`);
      if (s.overall < 0.8 && data.retry_count < 4) {
        addDetail(`🔁 Retry ${data.retry_count}/4 — rewriting patch…`);
      }
    }
  }
}

function pct(v) { return `${(v * 100).toFixed(0)}%`; }

function addDetail(text) {
  const p = document.createElement("p");
  p.style.margin = "4px 0";
  p.textContent = text;
  details.appendChild(p);
}

function render({ status, pr_url, error }) {
  box.className = "";
  if (status === "running") {
    box.classList.add("running");
    box.textContent = "⏳ Pipeline running…";
    prLink.style.display = "none";
  } else if (status === "success") {
    box.classList.add("success");
    box.textContent = "✅ Fix complete!";
    prLink.style.display = "block";
    prAnchor.href = pr_url;
  } else if (status === "failed") {
    box.classList.add("failed");
    box.textContent = `❌ Pipeline failed: ${error ?? "check backend logs"}`;
  } else if (status === "error") {
    box.classList.add("failed");
    box.textContent = "⚠️ Could not reach backend";
  }
}