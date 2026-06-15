function extractIssueData() {
  const title = document.querySelector('[data-testid="issue-title"]')?.innerText
    || document.querySelector('.js-issue-title')?.innerText
    || document.title;

  const body = document.querySelector('[data-testid="issue-body"]')?.innerText
    || document.querySelector('.markdown-body')?.innerText
    || document.querySelector('.comment-body')?.innerText
    || "";

  const url = window.location.href;
  const commentEls = document.querySelectorAll('.js-comment-body, [data-testid="comment-body"]');
  const comments = Array.from(commentEls)
    .slice(1)
    .map(el => el.innerText.trim())
    .filter(c => c.length > 0);

  const images = Array.from(
    document.querySelectorAll('.markdown-body img')
  ).map(img => img.src);

  return { issue_url: url, issue_title: title.trim(), issue_body: body.trim(), issue_comments: comments, issue_images: images };

}

console.log("[gitFixr] content script loaded on:", window.location.href);

// Wait for GitHub to finish rendering the issue body dynamically,
// then store the extracted data for the sidebar button to pick up.
// The pipeline does NOT start automatically — the user clicks "Fix this Issue".
setTimeout(() => {
  const data = extractIssueData();
  console.log("[gitFixr] extracted issue data:", data);
  // Clear any stale pipeline state from a previous run so the button always shows
  chrome.storage.local.set({ pending_issue: data, status: null, run_id: null, pr_url: null, error: null });
}, 2000);