const ingestVersionSelect = document.querySelector("#ingest-version");
const askVersionSelect = document.querySelector("#ask-version");
const chatProviderSelect = document.querySelector("#chat-provider");
const askForm = document.querySelector("#ask-form");
const queryInput = document.querySelector("#query");
const answerBox = document.querySelector("#answer");
const progressStagesBox = document.querySelector("#progress-stages");
const sourcesBox = document.querySelector("#sources");
const taskWorkspaceBox = document.querySelector("#task-workspace");
const ingestButton = document.querySelector("#ingest");
const resetButton = document.querySelector("#reset");
const historyListBox = document.querySelector("#history-list");
const historyAnswerBox = document.querySelector("#history-answer");
const historySourcesBox = document.querySelector("#history-sources");
const historyTaskWorkspaceBox = document.querySelector("#history-task-workspace");
const clearHistoryButton = document.querySelector("#clear-history");
const refreshHistoryButton = document.querySelector("#refresh-history");
let selectedHistoryId = null;
const chatProviderStorageKey = "docassist.chatProvider";

/**
 * Load documentation versions from the API and populate the version selector.
 */
async function loadVersions() {
  const response = await fetch("/api/versions");
  const payload = await response.json();
  const selects = [ingestVersionSelect, askVersionSelect].filter(Boolean);
  for (const select of selects) {
    select.innerHTML = "";
  }
  for (const version of payload.versions) {
    for (const select of selects) {
      const option = document.createElement("option");
      option.value = version;
      option.textContent = version.toUpperCase();
      option.selected = version === payload.default;
      select.append(option);
    }
  }
}

/**
 * Load available answer providers from the API and populate the provider selector.
 */
async function loadChatProviders() {
  if (!chatProviderSelect) {
    return;
  }

  const response = await fetch("/api/chat-providers");
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Chat provider request failed");
  }

  const remembered = localStorage.getItem(chatProviderStorageKey);
  const providers = Array.isArray(payload.providers) ? payload.providers : [];
  const selectedProvider = providers.includes(remembered) ? remembered : payload.default;
  chatProviderSelect.innerHTML = "";
  for (const provider of providers) {
    const option = document.createElement("option");
    option.value = provider;
    option.textContent = formatChatProvider(provider);
    option.selected = provider === selectedProvider;
    chatProviderSelect.append(option);
  }
}

if (askForm) {
  askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const selectedProvider = chatProviderSelect ? chatProviderSelect.value : "ollama";
    answerBox.textContent = "";
    resetProgressPanel();
    sourcesBox.innerHTML = "";
    taskWorkspaceBox.innerHTML = "";
    const button = askForm.querySelector("button[type='submit']");
    button.disabled = true;

    try {
      const response = await fetch("/api/ask/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          version: askVersionSelect.value,
          query: queryInput.value,
          chatProvider: selectedProvider,
          includeWorkspace: true,
        }),
      });
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || "Request failed");
      }
      await readAskEvents(response);
    } catch (error) {
      answerBox.textContent = error.message;
      taskWorkspaceBox.innerHTML = "";
    } finally {
      button.disabled = false;
    }
  });
}

/**
 * Read Server-Sent Events from the backend ask endpoint.
 */
async function readAskEvents(response) {
  if (!response.body) {
    throw new Error("This browser cannot read streaming responses.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const statusMessages = [];
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    buffer = processSseBuffer(buffer, statusMessages);
    if (done) {
      processSseBuffer(`${buffer}\n\n`, statusMessages);
      break;
    }
  }
}

/**
 * Parse complete SSE frames and return any incomplete trailing buffer.
 */
function processSseBuffer(buffer, statusMessages) {
  let remaining = buffer;
  let boundary = remaining.indexOf("\n\n");
  while (boundary !== -1) {
    const frame = remaining.slice(0, boundary);
    remaining = remaining.slice(boundary + 2);
    handleSseFrame(frame, statusMessages);
    boundary = remaining.indexOf("\n\n");
  }
  return remaining;
}

/**
 * Handle one SSE frame emitted by /api/ask/events.
 */
function handleSseFrame(frame, statusMessages) {
  const dataLines = frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data: "))
    .map((line) => line.slice(6));
  if (!dataLines.length) {
    return;
  }

  const payload = JSON.parse(dataLines.join("\n"));
  if (payload.type === "stage") {
    statusMessages.push(payload.message);
    answerBox.textContent = statusMessages.join("\n");
    updateProgressStage(payload.stage, {
      status: "Active",
      message: payload.message,
      elapsedMs: payload.elapsedMs,
      stepId: payload.stepId,
      stepTitle: payload.stepTitle,
    });
    return;
  }
  if (payload.type === "stage_complete") {
    updateProgressStage(payload.stage, {
      status: "Done",
      durationMs: payload.durationMs,
      elapsedMs: payload.elapsedMs,
      sources: payload.sources,
      stepId: payload.stepId,
      stepTitle: payload.stepTitle,
    });
    return;
  }
  if (payload.type === "complete") {
    answerBox.textContent = payload.answer || "No answer returned.";
    updateProgressTotal(payload.totalMs);
    renderSources(payload.sources || []);
    renderTaskWorkspace(payload.workspace);
    return;
  }
  if (payload.type === "error") {
    markProgressFailed(payload.message || "Request failed");
    throw new Error(payload.message || "Request failed");
  }
}

/**
 * Reset the visible backend progress table before a new question.
 */
function resetProgressPanel() {
  if (!progressStagesBox) {
    return;
  }

  progressStagesBox.innerHTML = `
    <div class="progress-table" role="table" aria-label="Answer progress">
      <div class="progress-row progress-heading" role="row">
        <span role="columnheader">Stage</span>
        <span role="columnheader">Status</span>
        <span role="columnheader">Duration</span>
      </div>
      ${progressStageDefinitions()
        .map(
          (stage) => `
            <div class="progress-row" data-stage="${stage.id}" role="row">
              <span role="cell">${escapeHtml(stage.label)}</span>
              <span role="cell" class="progress-status">Pending</span>
              <span role="cell" class="progress-duration">-</span>
            </div>
          `
        )
        .join("")}
      <div class="progress-row progress-total" data-stage="total" role="row">
        <span role="cell">Total</span>
        <span role="cell" class="progress-status">Pending</span>
        <span role="cell" class="progress-duration">-</span>
      </div>
    </div>
  `;
}

/**
 * Update one visible progress stage from backend timing events.
 */
function updateProgressStage(stage, details) {
  if (!progressStagesBox || !stage) {
    return;
  }

  const row = findOrCreateProgressRow(stage, details);
  if (!row) {
    return;
  }

  row.dataset.status = String(details.status || "").toLowerCase();
  const statusCell = row.querySelector(".progress-status");
  const durationCell = row.querySelector(".progress-duration");
  if (statusCell && details.status) {
    statusCell.textContent = details.status;
  }
  if (durationCell) {
    if (details.durationMs !== undefined) {
      const suffix = details.sources !== undefined ? `, ${details.sources} source${details.sources === 1 ? "" : "s"}` : "";
      durationCell.textContent = `${formatDuration(details.durationMs)}${suffix}`;
    } else if (details.elapsedMs !== undefined) {
      durationCell.textContent = `${formatDuration(details.elapsedMs)} elapsed`;
    }
  }
}

/**
 * Mark the total row once the complete event arrives.
 */
function updateProgressTotal(totalMs) {
  updateProgressStage("total", {
    status: "Done",
    durationMs: totalMs,
  });
}

/**
 * Mark the active row as failed when the backend emits an error.
 */
function markProgressFailed(message) {
  if (!progressStagesBox) {
    return;
  }

  const activeRow = progressStagesBox.querySelector('[data-status="active"]');
  const row = activeRow || progressStagesBox.querySelector('[data-stage="total"]');
  row.dataset.status = "failed";
  const statusCell = row.querySelector(".progress-status");
  const durationCell = row.querySelector(".progress-duration");
  if (statusCell) {
    statusCell.textContent = "Failed";
  }
  if (durationCell) {
    durationCell.textContent = message;
  }
}

/**
 * Stages displayed in the progress panel.
 */
function progressStageDefinitions() {
  return [
    { id: "prepare", label: "Preparing question" },
    { id: "plan", label: "Planning retrieval" },
    { id: "synthesize", label: "Synthesizing answer" },
    { id: "answer", label: "Generating answer" },
  ];
}

/**
 * Find a progress row, adding dynamic per-step rows as needed.
 */
function findOrCreateProgressRow(stage, details) {
  const rowKey = progressRowKey(stage, details);
  let row = progressStagesBox.querySelector(`[data-stage="${rowKey}"]`);
  if (row) {
    return row;
  }
  if (!details || !details.stepId) {
    return progressStagesBox.querySelector(`[data-stage="${stage}"]`);
  }

  const totalRow = progressStagesBox.querySelector('[data-stage="total"]');
  row = document.createElement("div");
  row.className = "progress-row";
  row.dataset.stage = rowKey;
  row.setAttribute("role", "row");
  const label = details.stepTitle ? `${details.stepId}: ${details.stepTitle}` : details.stepId;
  row.innerHTML = `
    <span role="cell">${escapeHtml(label)}</span>
    <span role="cell" class="progress-status">Pending</span>
    <span role="cell" class="progress-duration">-</span>
  `;
  totalRow.before(row);
  return row;
}

/**
 * Return the stable visible row key for a backend progress event.
 */
function progressRowKey(stage, details) {
  if (!details || !details.stepId) {
    return stage;
  }

  const visibleStage = stage === "step_retrieve" ? "step" : stage;
  return `${visibleStage}-${details.stepId}`;
}

/**
 * Format backend millisecond timings for users.
 */
function formatDuration(milliseconds) {
  if (milliseconds === undefined || milliseconds === null || Number.isNaN(Number(milliseconds))) {
    return "-";
  }
  return `${(Number(milliseconds) / 1000).toFixed(2)}s`;
}

if (chatProviderSelect) {
  chatProviderSelect.addEventListener("change", () => {
    localStorage.setItem(chatProviderStorageKey, chatProviderSelect.value);
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
        body: JSON.stringify({ version: ingestVersionSelect.value }),
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
    if (progressStagesBox) {
      progressStagesBox.innerHTML = "";
    }
    sourcesBox.innerHTML = "";
    taskWorkspaceBox.innerHTML = "";
    queryInput.focus();
  });
}

if (historyListBox) {
  renderHistoryPage().catch((error) => {
    historyListBox.innerHTML = `<p class="empty-note">${escapeHtml(error.message)}</p>`;
    renderHistoryDetail(null);
  });
}

if (refreshHistoryButton) {
  refreshHistoryButton.addEventListener("click", async () => {
    await refreshHistory();
  });
}

if (clearHistoryButton) {
  clearHistoryButton.addEventListener("click", async () => {
    clearHistoryButton.disabled = true;
    try {
      const response = await fetch("/api/history", { method: "DELETE" });
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || "Clear history failed");
      }
      await renderHistoryPage();
    } catch (error) {
      historyListBox.innerHTML = `<p class="empty-note">${escapeHtml(error.message)}</p>`;
      renderHistoryDetail(null);
    } finally {
      clearHistoryButton.disabled = false;
    }
  });
}

if (historyListBox) {
  window.addEventListener("focus", () => {
    refreshHistory();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      refreshHistory();
    }
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
      <div>
        <dt>Planner</dt>
        <dd>${escapeHtml(task.plannerMode || "deterministic")}</dd>
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
        ${steps.map(renderWorkspaceStep).join("")}
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
 * Render the saved question history and the selected entry detail.
 */
async function renderHistoryPage(selectedId) {
  selectedHistoryId = selectedId || selectedHistoryId;
  const response = await fetch("/api/history");
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "History request failed");
  }

  const history = Array.isArray(payload.history) ? payload.history : [];
  historyListBox.innerHTML = "";

  if (!history.length) {
    historyListBox.innerHTML = `<p class="empty-note">No saved queries yet.</p>`;
    selectedHistoryId = null;
    renderHistoryDetail(null);
    return;
  }

  const selected = history.find((item) => item.id === selectedHistoryId) || history[0];
  selectedHistoryId = selected.id;
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
 * Reload history without throwing into event handlers.
 */
async function refreshHistory() {
  if (!historyListBox) {
    return;
  }

  if (refreshHistoryButton) {
    refreshHistoryButton.disabled = true;
  }

  try {
    await renderHistoryPage();
  } catch (error) {
    historyListBox.innerHTML = `<p class="empty-note">${escapeHtml(error.message)}</p>`;
    renderHistoryDetail(null);
  } finally {
    if (refreshHistoryButton) {
      refreshHistoryButton.disabled = false;
    }
  }
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
 * Format provider ids for compact display in the toolbar.
 */
function formatChatProvider(provider) {
  if (provider === "nanogpt") {
    return "NanoGPT";
  }
  if (provider === "ollama") {
    return "Ollama";
  }
  return provider;
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
 * Render one multi-step workspace entry.
 */
function renderWorkspaceStep(step) {
  if (typeof step === "string") {
    return `<li>${escapeHtml(step)}</li>`;
  }
  const evidence = Array.isArray(step.evidence) ? step.evidence : [];
  const gaps = Array.isArray(step.gaps) ? step.gaps : [];
  return `
    <li>
      <strong>${escapeHtml(step.id || "")}: ${escapeHtml(step.title || "")}</strong>
      <p>${escapeHtml(step.result || step.description || "")}</p>
      <small>${escapeHtml(step.status || "pending")}</small>
      ${
        evidence.length
          ? `<ul>${evidence.map((item) => `<li>${escapeHtml(item.id || "")}: ${escapeHtml(item.path || "")}</li>`).join("")}</ul>`
          : ""
      }
      ${gaps.length ? `<ul>${gaps.map((gap) => `<li>${escapeHtml(gap)}</li>`).join("")}</ul>` : ""}
    </li>
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

if (ingestVersionSelect || askVersionSelect) {
  Promise.all([loadVersions(), loadChatProviders()]).catch((error) => {
    answerBox.textContent = error.message;
  });
}
