"""Web search via DuckDuckGo — no API key needed."""
import time
from typing import List, Dict

_BACKOFF = [2, 5, 10]  # retry delays in seconds


def _ddg_text(query: str, max_results: int) -> list:
    from duckduckgo_search import DDGS
    for attempt, wait in enumerate([0] + _BACKOFF):
        if wait:
            time.sleep(wait)
        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            msg = str(e)
            if "202" in msg or "403" in msg or "Ratelimit" in msg:
                print(f"[Search] Rate limited, retry {attempt+1}/3 in {_BACKOFF[attempt] if attempt < len(_BACKOFF) else 10}s")
                continue
            print(f"[Search] DuckDuckGo error: {e}")
            return []
    return []


def _ddg_news(query: str, max_results: int) -> list:
    from duckduckgo_search import DDGS
    for attempt, wait in enumerate([0] + _BACKOFF):
        if wait:
            time.sleep(wait)
        try:
            with DDGS() as ddgs:
                return list(ddgs.news(query, max_results=max_results))
        except Exception as e:
            msg = str(e)
            if "202" in msg or "403" in msg or "Ratelimit" in msg:
                print(f"[Search] News rate limited, retry {attempt+1}/3")
                continue
            print(f"[Search] News error: {e}")
            return []
    return []


def search_web(query: str, max_results: int = 8) -> List[Dict]:
    results = _ddg_text(query, max_results)
    return [{"title": r.get("title",""), "url": r.get("href",""),
             "body": r.get("body","")} for r in results]


def search_news(query: str, max_results: int = 5) -> List[Dict]:
    results = _ddg_news(query, max_results)
    return [{"title": r.get("title",""), "url": r.get("url",""),
             "body": r.get("body",""), "date": r.get("date","")} for r in results]


def search_trends(topic: str) -> List[str]:
    results = search_web(f"{topic} 2025 2026 trends insights", max_results=6)
    news    = search_news(f"{topic} latest", max_results=4)
    snippets = [r["body"][:200] for r in results + news if r.get("body")]
    return snippets[:8]
