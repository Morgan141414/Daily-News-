import argparse, asyncio, logging, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .config import Settings
from .monitoring import configure_logging
from .storage import Store
from .collectors import collect
from .processing import deduplicate, Summarizer, format_issue, is_fresh
from .telegram import TelegramDelivery
from .lifecycle import single_instance
log = logging.getLogger(__name__)
MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")

def next_issue_time(settings):
    now = datetime.now(ZoneInfo(settings.timezone)); target = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if target <= now: target += timedelta(days=1)
    return target

def run_once(settings, immediate=False):
    with single_instance(settings.root / "data/agent.lock") as acquired:
        if not acquired:
            log.warning("another Korgan Intelligence cycle is already running; skipping")
            return
        return _run_once(settings, immediate)

def _run_once(settings, immediate=False):
    settings.temp_dir.mkdir(parents=True, exist_ok=True); settings.news_dir.mkdir(parents=True, exist_ok=True)
    store = Store(settings.database_path); cutoff = time.time() - 86400; store.cleanup(cutoff); store.cleanup_news_files(settings.news_dir, cutoff)
    when = next_issue_time(settings); issue_date = when.date().isoformat(); existing = store.issue(issue_date)
    if immediate:
        issue_date = "test-" + datetime.now(ZoneInfo(settings.timezone)).strftime("%Y%m%d-%H%M%S")
    if not immediate and existing and existing["status"] in ("scheduled", "sent"):
        log.info("issue %s already %s", issue_date, existing["status"]); return
    collected = collect(settings)
    fresh = [article for article in collected if is_fresh(article, settings)]
    articles = deduplicate(fresh, settings)[:settings.max_items]
    if not articles:
        log.warning("no fresh articles; empty issue will not be sent")
        return
    summarizer = Summarizer(settings)
    for article in articles:
        article["summary"] = summarizer.summarize(article); store.save_article(article); store.update_summary(article["id"], article["summary"])
    body = format_issue(f"{when.day} {MONTHS[when.month - 1]}", articles)
    news_file = store.write_news_file(settings.news_dir, issue_date, collected, articles, body)
    try:
        ids = asyncio.run(TelegramDelivery(settings).send_now(body) if immediate else TelegramDelivery(settings).schedule(body, when))
    except Exception as exc:
        log.error("Telegram scheduling failed; keeping local draft: %s", exc)
        ids = []
    store.save_issue(issue_date, "sent" if immediate and ids else ("scheduled" if ids else "prepared"), body, datetime.now(ZoneInfo(settings.timezone)).isoformat() if immediate else when.isoformat(), ids)
    log.info("issue %s prepared with %d/%d articles; file=%s; telegram_ids=%s", issue_date, len(articles), len(collected), news_file, ids)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--once", action="store_true"); parser.add_argument("--authorize", action="store_true"); parser.add_argument("--list-dialogs", action="store_true"); parser.add_argument("--test-send-now", action="store_true"); args = parser.parse_args()
    settings = Settings.load(); configure_logging(settings.log_dir)
    if args.authorize:
        asyncio.run(TelegramDelivery(settings).authorize()); return
    if args.list_dialogs:
        for dialog_id, name, username in asyncio.run(TelegramDelivery(settings).list_dialogs()):
            print(f"{dialog_id}\t{name}\t@{username or '-'}")
        return
    run_once(settings, immediate=args.test_send_now)
