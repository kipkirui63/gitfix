const BACKEND_URL = "http://localhost:8001";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "FIX_ISSUE") {
    handleIssueDetected(message.payload, sendResponse);
    return true;  // keep message channel open for async response
  }
});

async function handleIssueDetected(payload, sendResponse) {
  try {
    // 1. POST issue to backend — get back a run_id immediately
    const res = await fetch(`${BACKEND_URL}/fix-issue`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const { run_id } = await res.json();

    // 2. Persist run_id so sidebar can read it when popup opens
    await chrome.storage.local.set({ run_id, status: "running", pr_url: null });

    console.log("[gitFixr] pipeline started, run_id:", run_id);
    sendResponse({ run_id });

    // 3. Poll /status/{run_id} every 3s until pipeline finishes
    _pollStatus(run_id);

  } catch (err) {
    console.error("[gitFixr] backend error:", err);
    await chrome.storage.local.set({ status: "error", error: err.message });
    sendResponse({ error: err.message });
  }
}

function _pollStatus(run_id) {
  const interval = setInterval(async () => {
    try {
      const res  = await fetch(`${BACKEND_URL}/status/${run_id}`);
      const data = await res.json();

      if (data.status === "success") {
        clearInterval(interval);
        await chrome.storage.local.set({ status: "success", pr_url: data.pr_url });
        // Notify the sidebar if it's currently open
        chrome.runtime.sendMessage({ type: "PIPELINE_UPDATE", payload: data });

      } else if (data.status === "failed") {
        clearInterval(interval);
        await chrome.storage.local.set({ status: "failed", error: data.error });
        chrome.runtime.sendMessage({ type: "PIPELINE_UPDATE", payload: data });
      }
      // else still "running" — keep polling

    } catch (err) {
      clearInterval(interval);
      console.error("[gitFixr] polling error:", err);
    }
  }, 3000);
}