import hashlib, json, sqlite3, time
from pathlib import Path

class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL, source TEXT,
          published_at TEXT, description TEXT, content TEXT, score REAL DEFAULT 0,
          summary TEXT, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS issues (
          issue_date TEXT PRIMARY KEY, status TEXT NOT NULL, body TEXT, telegram_ids TEXT,
          scheduled_at TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS articles_url ON articles(url);
        """)
        self.db.commit()

    @staticmethod
    def article_id(url, title):
        return hashlib.sha256((url.strip() + "\n" + title.strip().lower()).encode()).hexdigest()

    def save_article(self, article):
        self.db.execute("""INSERT OR IGNORE INTO articles
          (id,title,url,source,published_at,description,content,score,summary,created_at)
          VALUES (?,?,?,?,?,?,?,?,?,?)""", (article["id"], article["title"], article["url"], article.get("source"),
          article.get("published_at"), article.get("description"), article.get("content"), article.get("score", 0),
          article.get("summary"), time.time()))
        self.db.commit()

    def update_summary(self, article_id, summary):
        self.db.execute("UPDATE articles SET summary=? WHERE id=?", (summary, article_id)); self.db.commit()

    def article_exists(self, article_id):
        return self.db.execute("SELECT 1 FROM articles WHERE id=?", (article_id,)).fetchone() is not None

    def issue(self, date):
        return self.db.execute("SELECT * FROM issues WHERE issue_date=?", (date,)).fetchone()

    def save_issue(self, date, status, body, scheduled_at=None, telegram_ids=None):
        now = time.time()
        self.db.execute("""INSERT INTO issues(issue_date,status,body,telegram_ids,scheduled_at,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?) ON CONFLICT(issue_date) DO UPDATE SET status=excluded.status,body=excluded.body,
          telegram_ids=excluded.telegram_ids,scheduled_at=excluded.scheduled_at,updated_at=excluded.updated_at""",
          (date, status, body, json.dumps(telegram_ids or []), scheduled_at, now, now)); self.db.commit()

    def cleanup(self, cutoff):
        self.db.execute("DELETE FROM articles WHERE created_at < ?", (cutoff,)); self.db.commit()

    def issue_count(self):
        return self.db.execute("SELECT COUNT(*) FROM issues").fetchone()[0]

    @staticmethod
    def write_news_file(directory: Path, issue_date, collected, selected, body):
        """Write a human-inspectable, atomic snapshot of the latest collection."""
        directory.mkdir(parents=True, exist_ok=True)
        payload = {"issue_date": issue_date, "collected_count": len(collected), "selected_count": len(selected),
                   "collected": collected, "selected": selected, "issue": body}
        target = directory / f"{issue_date}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(target)
        return target

    @staticmethod
    def cleanup_news_files(directory: Path, cutoff):
        if not directory.exists(): return
        for path in directory.glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff: path.unlink()
            except OSError:
                pass
