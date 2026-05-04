const versionSelect = document.querySelector("#version");
const askForm = document.querySelector("#ask-form");
const queryInput = document.querySelector("#query");
const answerBox = document.querySelector("#answer");
const sourcesBox = document.querySelector("#sources");
const taskWorkspaceBox = document.querySelector("#task-workspace");
const ingestButton = document.querySelector("#ingest");
const resetButton = document.querySelector("#reset");
const historyListBox = document.querySelector("#history-list");
const historyAnswerBox = document.querySelector("#history-answer");
const historySourcesBox = document.querySelector("#history-sources");
const historyTaskWorkspaceBox = document.querySelector("#history-task-workspace");
const clearHistoryButton = document.querySelector("#clear-history");
const historyStorageKey = "docassist.queryHistory";
const historyLimit = 30;

/**
 * Load documentation versions from the API and populate the version selector.
 */
async function loadVersions() {
  const response = await fetch("/api/versions");
  const payload = await response.json();
  versionSelect.innerHTML = "";
  for (const version of payload.versions) {
    const option = document.createElement("option");
    option.value = version;
    option.textContent = version.toUpperCase();
    option.selected = version === payload.default;
    versionSelect.append(option);
  }
}

if (askForm) {
  askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    answerBox.textContent = "Searching local documentation...";
    sourcesBox.innerHTML = "";
    taskWorkspaceBox.innerHTML = "";
    const button = askForm.querySelector("button[type='submit']");
    button.disabled = true;

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          version: versionSelect.value,
          query: queryInput.value,
          includeWorkspace: true,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Request failed");
      }
      answerBox.textContent = payload.answer || "No answer returned.";
      renderSources(payload.sources || []);
      renderTaskWorkspace(payload.workspace);
      saveHistoryItem({
        id: createHistoryId(),
        version: versionSelect.value,
        question: queryInput.value,
        answer: payload.answer || "",
        sources: payload.sources || [],
        workspace: payload.workspace || null,
        createdAt: new Date().toISOString(),
      });
    } catch (error) {
      answerBox.textContent = error.message;
      taskWorkspaceBox.innerHTML = "";
    } finally {
      button.disabled = false;
    }
  });
}

if (ingestButton) {
  ingestButton.addEventListener("click", async () => {
    answerBox.textContent = "Ingesting documentation. This can take a while for full JDK docs...";
    sourcesBox.innerHTML = "";
    taskWorkspaceBox.innerHTML = "";
    ingestButton.disabled = true;
    try {
      const response = await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: versionSelect.value }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Ingest failed");
      }
      answerBox.textContent = `Ingested ${payload.documents} documents into ${payload.chunks} chunks.`;
    } catch (error) {
      answerBox.textContent = error.message;
    } finally {
      ingestButton.disabled = false;
    }
  });
}

if (resetButton) {
  resetButton.addEventListener("click", () => {
    queryInput.value = "";
    answerBox.textContent = "";
    sourcesBox.innerHTML = "";
    taskWorkspaceBox.innerHTML = "";
    queryInput.focus();
  });
}

if (historyListBox) {
  renderHistoryPage();
}

if (clearHistoryButton) {
  clearHistoryButton.addEventListener("click", () => {
    localStorage.removeItem(historyStorageKey);
    renderHistoryPage();
  });
}

/**
 * Render retrieved source snippets below the answer.
 *
 * The source data comes from the API, so values are escaped before entering the
 * HTML template.
 */
function renderSources(sources, target = sourcesBox) {
  if (!target) {
    return;
  }

  target.innerHTML = "";
  for (const source of sources) {
    const item = document.createElement("article");
    item.className = "source";
    item.innerHTML = `
      <strong>${escapeHtml(source.title || source.path)}</strong>
      <p>${escapeHtml(source.path)}</p>
      <p>${escapeHtml(source.snippet || "")}</p>
    `;
    target.append(item);
  }
}

/**
 * Render the temporary retrieval and synthesis workspace returned by the API.
 */
function renderTaskWorkspace(workspace, target = taskWorkspaceBox) {
  if (!target) {
    return;
  }

  target.innerHTML = "";
  if (!workspace || !workspace.task) {
    return;
  }

  const task = workspace.task;
  const evidence = Array.isArray(task.evidence) ? task.evidence : [];
  const steps = Array.isArray(task.steps) ? task.steps : [];
  const gaps = Array.isArray(task.gaps) ? task.gaps : [];

  const summary = document.createElement("div");
  summary.className = "task-summary";
  summary.innerHTML = `
    <dl>
      <div>
        <dt>Version</dt>
        <dd>${escapeHtml(task.version || "")}</dd>
      </div>
      <div>
        <dt>Intent</dt>
        <dd>${escapeHtml(task.intent || "")}</dd>
      </div>
    </dl>
  `;
  target.append(summary);

  if (steps.length) {
    const plan = document.createElement("div");
    plan.className = "task-plan";
    plan.innerHTML = `
      <h3>Plan</h3>
      <ol>
        ${steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}
      </ol>
    `;
    target.append(plan);
  }

  const evidenceList = document.createElement("div");
  evidenceList.className = "evidence-list";
  evidenceList.innerHTML = evidence.length
    ? evidence.map(renderEvidenceItem).join("")
    : `<p class="empty-note">No evidence retrieved.</p>`;
  target.append(evidenceList);

  if (gaps.length) {
    const gapList = document.createElement("div");
    gapList.className = "gap-list";
    gapList.innerHTML = `
      <h3>Gaps</h3>
      <ul>
        ${gaps.map((gap) => `<li>${escapeHtml(gap)}</li>`).join("")}
      </ul>
    `;
    target.append(gapList);
  }
}

/**
 * Persist one successful question and answer for the history page.
 */
function saveHistoryItem(item) {
  const history = loadHistory();
  history.unshift(item);
  localStorage.setItem(historyStorageKey, JSON.stringify(history.slice(0, historyLimit)));
}

/**
 * Load saved history entries, ignoring malformed localStorage data.
 */
function loadHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(historyStorageKey) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/**
 * Render the saved question history and the selected entry detail.
 */
function renderHistoryPage(selectedId) {
  const history = loadHistory();
  historyListBox.innerHTML = "";

  if (!history.length) {
    historyListBox.innerHTML = `<p class="empty-note">No saved queries yet.</p>`;
    renderHistoryDetail(null);
    return;
  }

  const selected = history.find((item) => item.id === selectedId) || history[0];
  for (const item of history) {
    const button = document.createElement("button");
    button.className = item.id === selected.id ? "history-item active" : "history-item";
    button.type = "button";
    button.innerHTML = `
      <span>${escapeHtml(formatHistoryDate(item.createdAt))}</span>
      <strong>${escapeHtml(item.question || "Untitled question")}</strong>
      <small>${escapeHtml(item.version || "")}</small>
    `;
    button.addEventListener("click", () => renderHistoryPage(item.id));
    historyListBox.append(button);
  }

  renderHistoryDetail(selected);
}

/**
 * Render one saved history entry into the detail panels.
 */
function renderHistoryDetail(item) {
  if (!historyAnswerBox || !historySourcesBox || !historyTaskWorkspaceBox) {
    return;
  }

  if (!item) {
    historyAnswerBox.textContent = "";
    historySourcesBox.innerHTML = "";
    historyTaskWorkspaceBox.innerHTML = "";
    return;
  }

  historyAnswerBox.textContent = item.answer || "No answer saved.";
  renderSources(item.sources || [], historySourcesBox);
  renderTaskWorkspace(item.workspace, historyTaskWorkspaceBox);
}

/**
 * Build a compact history identifier without requiring a server round trip.
 */
function createHistoryId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/**
 * Format a saved timestamp for display in history.
 */
function formatHistoryDate(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}

/**
 * Render one evidence board item as escaped HTML.
 */
function renderEvidenceItem(item) {
  const score = item.score === null || item.score === undefined ? "unknown" : Number(item.score).toFixed(3);
  return `
    <article class="evidence-item">
      <div class="evidence-heading">
        <span>${escapeHtml(item.id || "")}</span>
        <strong>${escapeHtml(item.title || item.path || "")}</strong>
        <small>${escapeHtml(score)}</small>
      </div>
      <p class="evidence-path">${escapeHtml(item.path || "")}</p>
      <p>${escapeHtml(item.snippet || "")}</p>
      <p class="evidence-note">${escapeHtml(item.relevanceNote || "")}</p>
    </article>
  `;
}

/**
 * Escape text before interpolating it into HTML generated by this page.
 */
function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

if (versionSelect) {
  loadVersions().catch((error) => {
    answerBox.textContent = error.message;
  });
}
