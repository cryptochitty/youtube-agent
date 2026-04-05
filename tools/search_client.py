"""Web search via DuckDuckGo — no API key needed."""
from typing import List, Dict


def search_web(query: str, max_results: int = 8) -> List[Dict]:
    """Return list of {title, url, body} results."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r.get("title",""), "url": r.get("href",""),
                 "body": r.get("body","")} for r in results]
    except Exception as e:
        print(f"[Search] DuckDuckGo error: {e}")
        return []


def search_news(query: str, max_results: int = 5) -> List[Dict]:
    """Return recent news results."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        return [{"title": r.get("title",""), "url": r.get("url",""),
                 "body": r.get("body",""), "date": r.get("date","")} for r in results]
    except Exception as e:
        print(f"[Search] News error: {e}")
        return []


def search_trends(topic: str) -> List[str]:
    """Extract trending angles/hooks for a topic."""
    results = search_web(f"{topic} 2025 2026 trends insights", max_results=6)
    news    = search_news(f"{topic} latest", max_results=4)
    snippets = [r["body"][:200] for r in results + news if r.get("body")]
    return snippets[:8]
