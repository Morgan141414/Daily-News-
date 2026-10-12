import html, logging, re
import feedparser, httpx
from bs4 import BeautifulSoup
from .processing import valid_url
log = logging.getLogger(__name__)

def _article(title, url, source, published=None, description="", content=""):
    from .storage import Store
    clean = BeautifulSoup(html.unescape(content or description or ""), "html.parser").get_text(" ", strip=True)
    if not valid_url(url) or not title.strip():
        raise ValueError("invalid article URL or title")
    return {"id": Store.article_id(url, title), "title": re.sub(r"\s+", " ", title).strip(), "url": url,
            "source": source, "published_at": published, "description": description[:4000], "content": clean[:12000]}

def rss(source):
    feed = feedparser.parse(source["url"])
    result = []
    for item in feed.entries[:40]:
        content = item.get("content", [{}])[0].get("value", "") if item.get("content") else ""
        result.append(_article(item.get("title", ""), item.get("link", ""), source["name"], item.get("published", item.get("updated")), item.get("summary", ""), content))
    return result

def arxiv(source):
    r = httpx.get("https://export.arxiv.org/api/query", params={"search_query": source["query"], "start": 0, "max_results": source.get("max_results", 20), "sortBy": "submittedDate", "sortOrder": "descending"}, timeout=25)
    feed = feedparser.parse(r.text)
    return [_article(i.title, i.link, source["name"], i.get("published"), i.get("summary", ""), i.get("summary", "")) for i in feed.entries]

def crossref(source):
    r = httpx.get("https://api.crossref.org/works", params={"query": source.get("query", "quantum computing"), "rows": source.get("max_results", 15), "sort": "published", "order": "desc"}, timeout=25)
    result = []
    for i in r.json().get("message", {}).get("items", []):
        title = (i.get("title") or [""])[0]; url = i.get("URL", "")
        result.append(_article(title, url, source["name"], str(i.get("published", {}).get("date-parts", [[""]])[0]), i.get("abstract", "")))
    return result

def github(source):
    r = httpx.get("https://api.github.com/search/repositories", params={"q": source.get("query", "topic:artificial-intelligence"), "sort": "updated", "order": "desc", "per_page": source.get("max_results", 10)}, headers={"Accept": "application/vnd.github+json", "User-Agent": "korgan-intelligence"}, timeout=25)
    return [_article(i["full_name"], i["html_url"], source["name"], i.get("updated_at"), i.get("description", "")) for i in r.json().get("items", [])]

COLLECTORS = {"rss": rss, "arxiv": arxiv, "crossref": crossref, "github": github}

def collect(settings):
    result = []
    for source in settings.source_config().get("sources", []):
        try:
            fn = COLLECTORS.get(source.get("type"))
            if fn: result.extend(fn(source))
        except Exception as exc:
            log.warning("source %s unavailable: %s", source.get("name"), exc)
    return result
