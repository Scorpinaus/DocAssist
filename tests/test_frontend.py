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
