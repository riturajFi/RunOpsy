from __future__ import annotations


def render_home_page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Runopsy</title>
  <style>
    :root {
      --bg: #07120c;
      --bg-soft: #0e1d15;
      --card: rgba(14, 33, 22, 0.9);
      --card-strong: rgba(18, 42, 28, 0.96);
      --line: rgba(146, 255, 189, 0.16);
      --text: #ebfff0;
      --muted: #9bc8aa;
      --accent: #86f2a4;
      --accent-strong: #59df84;
      --accent-dim: rgba(134, 242, 164, 0.18);
      --danger: #ff9b9b;
      --shadow: inset 0 0 40px rgba(134, 242, 164, 0.12), inset 0 1px 0 rgba(212, 255, 224, 0.08);
      --font-sans: "Space Grotesk", "Segoe UI", sans-serif;
      --font-mono: "JetBrains Mono", "SFMono-Regular", monospace;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: var(--font-sans);
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(95, 255, 156, 0.14), transparent 28%),
        radial-gradient(circle at 80% 20%, rgba(74, 201, 115, 0.16), transparent 22%),
        radial-gradient(circle at bottom, rgba(20, 55, 35, 0.9), transparent 34%),
        linear-gradient(180deg, #041008 0%, #07120c 45%, #09150e 100%);
      overflow-x: hidden;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(145, 255, 188, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(145, 255, 188, 0.03) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: radial-gradient(circle at center, black 40%, transparent 85%);
    }

    main {
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 32px 18px;
    }

    .shell {
      width: min(980px, 100%);
      position: relative;
    }

    .hero {
      text-align: center;
      margin-bottom: 22px;
      opacity: 0.95;
    }

    .eyebrow {
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 7px 12px;
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--muted);
      background: rgba(19, 45, 29, 0.54);
      backdrop-filter: blur(12px);
    }

    h1 {
      margin: 18px 0 10px;
      font-size: clamp(42px, 8vw, 92px);
      line-height: 0.92;
      letter-spacing: -0.05em;
      font-weight: 700;
    }

    .subtitle {
      margin: 0 auto;
      max-width: 620px;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.65;
    }

    .stage {
      position: relative;
      min-height: 420px;
    }

    .panel {
      width: min(760px, 100%);
      margin: 0 auto;
      transition: opacity 380ms ease, transform 380ms ease, filter 380ms ease;
    }

    .composer {
      position: relative;
      padding: 22px;
      border-radius: 28px;
      background: linear-gradient(180deg, rgba(14, 32, 22, 0.94), rgba(10, 24, 17, 0.96));
      border: 1px solid rgba(155, 255, 190, 0.14);
      box-shadow:
        0 40px 110px rgba(0, 0, 0, 0.34),
        0 0 0 1px rgba(190, 255, 211, 0.03),
        var(--shadow);
      backdrop-filter: blur(18px);
    }

    .composer.hidden {
      opacity: 0;
      transform: translateY(-18px) scale(0.985);
      pointer-events: none;
      filter: blur(8px);
    }

    .composer-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 16px;
      color: var(--muted);
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .status-dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 18px rgba(134, 242, 164, 0.8);
    }

    .input-shell {
      display: grid;
      gap: 14px;
      padding: 18px;
      border-radius: 22px;
      background:
        radial-gradient(circle at top, rgba(130, 255, 176, 0.14), transparent 45%),
        linear-gradient(180deg, rgba(18, 43, 28, 0.72), rgba(10, 22, 15, 0.82));
      border: 1px solid rgba(142, 255, 186, 0.14);
      box-shadow:
        inset 0 0 34px rgba(111, 255, 163, 0.14),
        inset 0 -10px 18px rgba(0, 0, 0, 0.18);
    }

    textarea {
      width: 100%;
      min-height: 160px;
      resize: none;
      border: 0;
      outline: 0;
      background: transparent;
      color: var(--text);
      font: 500 18px/1.6 var(--font-sans);
    }

    textarea::placeholder {
      color: rgba(225, 255, 234, 0.38);
    }

    .composer-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }

    .hint {
      color: var(--muted);
      font-size: 13px;
    }

    .hint code {
      font-family: var(--font-mono);
      color: var(--text);
      background: rgba(132, 255, 180, 0.1);
      border: 1px solid rgba(132, 255, 180, 0.08);
      padding: 2px 6px;
      border-radius: 8px;
    }

    button {
      appearance: none;
      border: 0;
      outline: 0;
      padding: 13px 18px;
      border-radius: 14px;
      background: linear-gradient(180deg, var(--accent), var(--accent-strong));
      color: #041008;
      font: 700 14px/1 var(--font-sans);
      letter-spacing: 0.06em;
      text-transform: uppercase;
      cursor: pointer;
      box-shadow: 0 12px 28px rgba(89, 223, 132, 0.28);
      transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
    }

    button:hover {
      transform: translateY(-1px);
      box-shadow: 0 18px 34px rgba(89, 223, 132, 0.34);
      filter: saturate(1.05);
    }

    .loading-panel,
    .result-panel {
      opacity: 0;
      pointer-events: none;
      transform: translateY(24px);
    }

    .loading-panel.visible,
    .result-panel.visible {
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0);
    }

    .loading-card,
    .result-card {
      border-radius: 30px;
      border: 1px solid rgba(144, 255, 188, 0.12);
      background: linear-gradient(180deg, rgba(12, 29, 20, 0.95), rgba(8, 18, 13, 0.98));
      box-shadow:
        0 40px 110px rgba(0, 0, 0, 0.4),
        inset 0 0 28px rgba(111, 255, 163, 0.08);
      overflow: hidden;
    }

    .loading-card {
      display: grid;
      place-items: center;
      min-height: 360px;
      text-align: center;
      padding: 36px 24px;
    }

    .loader {
      position: relative;
      width: 112px;
      height: 112px;
      margin: 0 auto 24px;
    }

    .loader::before,
    .loader::after {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: 50%;
      border: 2px solid transparent;
    }

    .loader::before {
      border-top-color: var(--accent);
      border-right-color: rgba(134, 242, 164, 0.35);
      animation: spin 1.2s linear infinite;
      box-shadow: 0 0 40px rgba(134, 242, 164, 0.2);
    }

    .loader::after {
      inset: 14px;
      border-bottom-color: rgba(134, 242, 164, 0.8);
      border-left-color: rgba(134, 242, 164, 0.24);
      animation: spinReverse 1.5s linear infinite;
    }

    .loading-title {
      font-size: clamp(24px, 3vw, 32px);
      letter-spacing: -0.04em;
      margin-bottom: 10px;
    }

    .loading-subtitle {
      color: var(--muted);
      max-width: 420px;
      margin: 0 auto;
      font-size: 15px;
      line-height: 1.7;
      min-height: 52px;
    }

    .pulse {
      animation: pulseText 1.4s ease-in-out infinite;
    }

    .result-card {
      padding: 28px;
    }

    .result-top {
      display: flex;
      gap: 16px;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }

    .result-title {
      font-size: clamp(28px, 5vw, 44px);
      line-height: 0.96;
      letter-spacing: -0.05em;
      margin: 0 0 8px;
    }

    .result-meta {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.7;
    }

    .result-reset {
      background: rgba(134, 242, 164, 0.1);
      color: var(--text);
      border: 1px solid rgba(134, 242, 164, 0.16);
      box-shadow: none;
    }

    .analysis-surface {
      border-radius: 22px;
      padding: 20px;
      background:
        linear-gradient(180deg, rgba(18, 40, 28, 0.68), rgba(8, 19, 14, 0.88));
      border: 1px solid rgba(145, 255, 188, 0.1);
      box-shadow: inset 0 0 24px rgba(111, 255, 163, 0.08);
    }

    .analysis-lines {
      display: grid;
      gap: 10px;
      color: #eefff1;
      font-size: 15px;
      line-height: 1.8;
    }

    .analysis-line {
      opacity: 0;
      transform: translateY(6px);
      animation: revealLine 500ms ease forwards;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .analysis-line code {
      font-family: var(--font-mono);
      font-size: 0.92em;
      background: rgba(134, 242, 164, 0.08);
      border: 1px solid rgba(134, 242, 164, 0.08);
      padding: 2px 6px;
      border-radius: 7px;
    }

    .error {
      margin-top: 14px;
      color: var(--danger);
      font-size: 14px;
      min-height: 20px;
    }

    .footer-note {
      margin-top: 16px;
      color: rgba(185, 223, 197, 0.72);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    @keyframes spinReverse {
      to { transform: rotate(-360deg); }
    }

    @keyframes pulseText {
      0%, 100% { opacity: 0.45; }
      50% { opacity: 1; }
    }

    @keyframes revealLine {
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @media (max-width: 720px) {
      .composer,
      .result-card,
      .loading-card {
        border-radius: 24px;
      }

      textarea {
        min-height: 140px;
        font-size: 16px;
      }
    }
  </style>
</head>
<body>
  <main>
    <div class="shell">
      <section class="hero">
        <div class="eyebrow">GitHub Actions Failure Reader</div>
        <h1>Runopsy</h1>
        <p class="subtitle">
          Paste a GitHub pull request URL and get back a focused failure analysis for the most relevant failed job.
        </p>
      </section>

      <section class="stage">
        <div class="panel composer" id="composerPanel">
          <div class="composer-top">
            <span>PR Analysis Input</span>
            <span class="status-dot" aria-hidden="true"></span>
          </div>
          <div class="input-shell">
            <textarea
              id="prInput"
              spellcheck="false"
              placeholder="https://github.com/owner/repo/pull/123"
            ></textarea>
            <div class="composer-actions">
              <div class="hint">Paste a pull request URL and press <code>Enter</code> to analyze.</div>
              <button id="analyzeButton" type="button">Analyze Failure</button>
            </div>
          </div>
          <div class="error" id="composerError"></div>
        </div>

        <div class="panel loading-panel" id="loadingPanel" aria-live="polite">
          <div class="loading-card">
            <div>
              <div class="loader" aria-hidden="true"></div>
              <div class="loading-title">Analyzing the GitHub Actions failure</div>
              <p class="loading-subtitle pulse" id="loadingText">
                Inspecting workflow runs, isolating the failed job, and preparing the analysis.
              </p>
            </div>
          </div>
        </div>

        <div class="panel result-panel" id="resultPanel">
          <div class="result-card">
            <div class="result-top">
              <div>
                <h2 class="result-title">Analysis Ready</h2>
                <div class="result-meta" id="resultMeta"></div>
              </div>
              <button class="result-reset" id="resetButton" type="button">Analyze Another PR</button>
            </div>
            <div class="analysis-surface">
              <div class="analysis-lines" id="analysisLines"></div>
            </div>
            <div class="footer-note">Generated by Runopsy</div>
          </div>
        </div>
      </section>
    </div>
  </main>

  <script>
    const composerPanel = document.getElementById("composerPanel");
    const loadingPanel = document.getElementById("loadingPanel");
    const resultPanel = document.getElementById("resultPanel");
    const prInput = document.getElementById("prInput");
    const analyzeButton = document.getElementById("analyzeButton");
    const resetButton = document.getElementById("resetButton");
    const composerError = document.getElementById("composerError");
    const loadingText = document.getElementById("loadingText");
    const resultMeta = document.getElementById("resultMeta");
    const analysisLines = document.getElementById("analysisLines");

    const loadingMessages = [
      "Inspecting workflow runs, isolating the failed job, and preparing the analysis.",
      "Pulling the most relevant failed log and trimming away downstream noise.",
      "Running the LLM pass over the log stream and extracting the likely root cause."
    ];

    let loadingIndex = 0;
    let loadingTimer = null;

    function startLoadingCopy() {
      stopLoadingCopy();
      loadingText.textContent = loadingMessages[0];
      loadingIndex = 0;
      loadingTimer = window.setInterval(() => {
        loadingIndex = (loadingIndex + 1) % loadingMessages.length;
        loadingText.textContent = loadingMessages[loadingIndex];
      }, 1800);
    }

    function stopLoadingCopy() {
      if (loadingTimer) {
        window.clearInterval(loadingTimer);
        loadingTimer = null;
      }
    }

    function escapeHtml(text) {
      return text
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function formatInlineCode(text) {
      return escapeHtml(text).replace(/`([^`]+)`/g, "<code>$1</code>");
    }

    function renderAnalysis(text) {
      analysisLines.innerHTML = "";
      const lines = text
        .split(/\\n{2,}|\\n/)
        .map((line) => line.trim())
        .filter(Boolean);

      lines.forEach((line, index) => {
        const element = document.createElement("div");
        element.className = "analysis-line";
        element.style.animationDelay = `${index * 90}ms`;
        element.innerHTML = formatInlineCode(line);
        analysisLines.appendChild(element);
      });
    }

    function showComposer(errorMessage = "") {
      stopLoadingCopy();
      composerPanel.classList.remove("hidden");
      loadingPanel.classList.remove("visible");
      resultPanel.classList.remove("visible");
      composerError.textContent = errorMessage;
      analyzeButton.disabled = false;
      analyzeButton.textContent = "Analyze Failure";
    }

    function showLoading() {
      composerError.textContent = "";
      composerPanel.classList.add("hidden");
      resultPanel.classList.remove("visible");
      loadingPanel.classList.add("visible");
      analyzeButton.disabled = true;
      analyzeButton.textContent = "Analyzing...";
      startLoadingCopy();
    }

    function showResult(payload) {
      stopLoadingCopy();
      resultMeta.innerHTML = [
        payload.pr_url ? `PR: <strong>${escapeHtml(payload.pr_url)}</strong>` : "",
        payload.request_id ? `Request ID: <strong>${escapeHtml(payload.request_id)}</strong>` : "",
        payload.run_id ? `Run ID: <strong>${escapeHtml(payload.run_id)}</strong>` : ""
      ].filter(Boolean).join("<br />");
      renderAnalysis(payload.analysis || "No analysis was returned.");
      loadingPanel.classList.remove("visible");
      resultPanel.classList.add("visible");
    }

    async function submitAnalysis() {
      const prUrl = prInput.value.trim();
      if (!prUrl) {
        composerError.textContent = "Paste a GitHub PR URL before starting the analysis.";
        prInput.focus();
        return;
      }

      showLoading();

      try {
        const response = await fetch("/api/v1/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pr_url: prUrl })
        });

        const payload = await response.json();
        if (!response.ok) {
          const detail = payload.detail;
          const message = typeof detail === "string"
            ? detail
            : detail?.message || "The analysis request failed.";
          throw new Error(message);
        }

        showResult(payload);
      } catch (error) {
        showComposer(error.message || "The analysis request failed.");
      }
    }

    analyzeButton.addEventListener("click", submitAnalysis);
    resetButton.addEventListener("click", () => {
      prInput.value = "";
      analysisLines.innerHTML = "";
      resultMeta.innerHTML = "";
      showComposer();
      prInput.focus();
    });

    prInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submitAnalysis();
      }
    });

    window.addEventListener("beforeunload", stopLoadingCopy);
    prInput.focus();
  </script>
</body>
</html>
"""
