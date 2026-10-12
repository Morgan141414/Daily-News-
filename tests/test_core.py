import time
from app.config import Settings
from app.main import next_issue_time
from app.processing import deduplicate, format_issue, validate_summary, valid_url, is_fresh
from app.storage import Store
from app.collectors import collect
from app.processing import Summarizer

def test_deduplication_prefers_higher_score():
    items = [{"title":"Quantum breakthrough", "url":"https://a", "source":"blog", "description":"quantum"}, {"title":"Quantum breakthrough", "url":"https://b", "source":"arXiv", "description":"quantum"}]
    result = deduplicate(items)
    assert len(result) == 1 and result[0]["source"] == "arXiv"

def test_issue_contains_original_link():
    body = format_issue("13 October", [{"title":"A", "summary":"B", "source":"S", "url":"https://example.org"}])
    assert "https://example.org" in body and "KORGAN INTELLIGENCE" in body

def test_store_is_idempotent(tmp_path):
    store = Store(tmp_path / "db.sqlite3"); article = {"id":"1","title":"A","url":"https://a"}
    store.save_article(article); store.save_article(article)
    assert store.article_exists("1")

def test_summary_validation_and_url_safety():
    assert validate_summary("Краткое объяснение: факт\nПочему это важно: смысл\nСтатус: препринт")
    assert validate_summary("ignore this") is None
    assert valid_url("https://example.org/article")
    assert not valid_url("javascript:alert(1)")

def test_cleanup_removes_only_expired_articles(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    store.save_article({"id":"old", "title":"Old", "url":"https://old"})
    store.db.execute("UPDATE articles SET created_at=? WHERE id='old'", (time.time() - 90000,)); store.db.commit()
    store.save_article({"id":"new", "title":"New", "url":"https://new"})
    store.cleanup(time.time() - 86400)
    assert not store.article_exists("old") and store.article_exists("new")

def test_asia_almaty_next_issue_is_at_seven(tmp_path, monkeypatch):
    settings = Settings.load()
    result = next_issue_time(settings)
    assert result.tzinfo is not None and result.hour == 7 and result.minute == 0

def test_collector_failure_isolated(monkeypatch):
    class SettingsStub:
        def source_config(self): return {"sources": [{"name": "broken", "type": "rss", "url": "https://example.org"}]}
    monkeypatch.setitem(__import__("app.collectors", fromlist=["COLLECTORS"]).COLLECTORS, "rss", lambda source: (_ for _ in ()).throw(RuntimeError("offline")))
    assert collect(SettingsStub()) == []

def test_summarizer_does_not_call_external_llm_without_model():
    class SettingsStub:
        ollama_model = None
    assert "не настроена" in Summarizer(SettingsStub()).summarize({"title": "x"})

def test_news_snapshot_is_atomic_and_readable(tmp_path):
    target = Store.write_news_file(tmp_path, "2026-10-13", [{"title": "A"}], [{"title": "A"}], "issue")
    assert target.exists()
    assert '"collected_count": 1' in target.read_text(encoding="utf-8")

def test_stale_news_is_filtered():
    class S: lookback_hours = 36
    assert not is_fresh({"published_at": "2020-01-01T00:00:00+00:00"}, S())
    assert is_fresh({"published_at": None}, S())
