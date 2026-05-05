from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_index_separates_ingest_and_ask_controls():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert 'id="ingest-version"' in html
    assert 'id="ask-version"' in html
    assert 'id="chat-provider"' in html
    ingest_panel = html[html.index('id="ingest-panel"') : html.index('id="ask-form"')]
    ask_panel = html[html.index('id="ask-form"') :]

    assert 'for="ingest-version"' in ingest_panel
    assert 'for="ask-version"' not in ingest_panel
    assert 'for="chat-provider"' not in ingest_panel
    assert 'for="ask-version"' in ask_panel
    assert 'for="chat-provider"' in ask_panel


def test_app_js_sends_ingest_and_ask_versions_separately():
    script = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'const ingestVersionSelect = document.querySelector("#ingest-version");' in script
    assert 'const askVersionSelect = document.querySelector("#ask-version");' in script
    assert "version: ingestVersionSelect.value" in script
    assert "version: askVersionSelect.value" in script
    assert "stepId: payload.stepId" in script


def test_index_exposes_advanced_ask_options():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    ask_panel = html[html.index('id="ask-form"') :]

    assert 'id="advanced-options-toggle"' in ask_panel
    assert 'aria-controls="advanced-options"' in ask_panel
    assert 'id="advanced-options" class="advanced-controls" hidden' in ask_panel
    assert 'id="temperature"' in ask_panel
    assert 'id="top-p"' in ask_panel
    assert 'id="max-tokens"' in ask_panel
    assert 'id="frequency-penalty"' in ask_panel
    assert 'id="presence-penalty"' in ask_panel
    assert 'id="reasoning-effort"' in ask_panel
    assert 'id="context-window"' in ask_panel
    assert 'id="top-k-results"' in ask_panel
    assert 'id="reset-options"' in ask_panel


def test_app_js_sends_advanced_ask_options():
    script = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'const temperatureInput = document.querySelector("#temperature");' in script
    assert 'const advancedOptionsToggle = document.querySelector("#advanced-options-toggle");' in script
    assert 'advancedOptionsPanel.hidden = isExpanded;' in script
    assert "options: readAskOptions()" in script
    assert "function readAskOptions()" in script
    assert "temperature: readNumberInput(temperatureInput)" in script
    assert "topP: readNumberInput(topPInput)" in script
    assert "maxTokens: readIntegerInput(maxTokensInput)" in script
    assert "frequencyPenalty: readNumberInput(frequencyPenaltyInput)" in script
    assert "presencePenalty: readNumberInput(presencePenaltyInput)" in script
    assert "reasoningEffort: readTextInput(reasoningEffortSelect)" in script
    assert "contextWindow: readIntegerInput(contextWindowInput)" in script
    assert "topKResults: readIntegerInput(topKResultsInput)" in script


def test_step_retrieval_progress_reuses_step_row():
    script = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "function progressRowKey(stage, details)" in script
    assert 'stage === "step_retrieve" ? "step" : stage' in script
    assert "const rowKey = progressRowKey(stage, details);" in script


def test_answer_sections_use_renderable_containers():
    index_html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    history_html = (PROJECT_ROOT / "frontend" / "history.html").read_text(encoding="utf-8")

    assert '<div id="answer" class="answer-content"></div>' in index_html
    assert '<pre id="answer"></pre>' not in index_html
    assert '<div id="history-answer" class="answer-content"></div>' in history_html
    assert '<pre id="history-answer"></pre>' not in history_html


def test_app_js_renders_markdown_code_fences_for_answers():
    script = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "function renderAnswer(markdown, target = answerBox)" in script
    assert "function splitMarkdownCodeFences(markdown)" in script
    assert '<pre class="answer-code"><code${languageClass}>${escapeHtml(part.content)}</code></pre>' in script
    assert 'renderAnswer(payload.answer || "No answer returned.")' in script
    assert 'renderAnswer(item.answer || "No answer saved.", historyAnswerBox)' in script
    assert 'answerBox.textContent = payload.answer || "No answer returned."' not in script
