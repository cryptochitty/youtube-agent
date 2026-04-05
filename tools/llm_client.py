"""
Lightweight LLM client — direct HTTP calls, no LangChain/LangGraph.
Groq (free) → Ollama (local) → fallback stub.
Saves ~300MB RAM vs langchain stack.
"""
import json, re, time, requests
from config import LLM_PROVIDER, GROQ_API_KEY, GROQ_MODEL, OLLAMA_URL, OLLAMA_MODEL


def invoke_llm(prompt: str, system: str = "", _attempt: int = 0,
               max_tokens: int = 4096) -> str:
    """Call LLM and return text response. Auto-retries on 429 with backoff."""
    try:
        if LLM_PROVIDER == "groq" and GROQ_API_KEY:
            return _groq(prompt, system, max_tokens)
        if LLM_PROVIDER in ("ollama", "groq"):
            return _ollama(prompt, system)
        if LLM_PROVIDER == "openai":
            return _openai(prompt, system, max_tokens)
        return _stub(prompt)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 413:
            raise  # payload too large — caller must reduce input
        if e.response is not None and e.response.status_code == 429 and _attempt < 5:
            # Respect retry-after header if present, else use exponential backoff
            retry_after = e.response.headers.get("retry-after") or e.response.headers.get("x-ratelimit-reset-requests")
            try:
                wait = max(int(float(retry_after)), 5) if retry_after else 30 * (2 ** _attempt)
            except (ValueError, TypeError):
                wait = 30 * (2 ** _attempt)
            wait = min(wait, 300)  # cap at 5 minutes
            print(f"[LLM] 429 rate limit — waiting {wait}s (attempt {_attempt+1}/5)...")
            time.sleep(wait)
            return invoke_llm(prompt, system, _attempt + 1)
        raise


def invoke_json(prompt: str, system: str = "", retries: int = 2,
                max_tokens: int = 4096) -> dict:
    """Call LLM, parse and return JSON dict. Never raises — returns {} on any error."""
    for attempt in range(retries + 1):
        try:
            raw = invoke_llm(
                prompt + "\n\nRespond ONLY with valid JSON. No markdown, no explanation.",
                system,
                max_tokens=max_tokens,
            )
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 413:
                print(f"[LLM] invoke_json: 413 payload too large — skipping")
                return {}
            raise
        except Exception as e:
            print(f"[LLM] invoke_json error: {e}")
            return {}
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{[\s\S]+\}', raw)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
        if attempt == retries:
            print(f"[LLM] JSON parse failed. Raw: {raw[:200]}")
            return {}
    return {}


# ── Groq (free tier — llama3, mixtral) ───────────────────────────────────────
_last_groq_call = 0.0

def _groq(prompt: str, system: str, max_tokens: int = 4096) -> str:
    global _last_groq_call
    # Throttle: minimum 3s between Groq calls to stay under rate limits
    elapsed = time.time() - _last_groq_call
    if elapsed < 3:
        time.sleep(3 - elapsed)
    _last_groq_call = time.time()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": GROQ_MODEL, "messages": messages,
              "temperature": 0.7, "max_tokens": max_tokens},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# ── Ollama (local) ────────────────────────────────────────────────────────────
def _ollama(prompt: str, system: str) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


# ── OpenAI ────────────────────────────────────────────────────────────────────
def _openai(prompt: str, system: str, max_tokens: int = 4096) -> str:
    from config import OPENAI_KEY, OPENAI_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}",
                 "Content-Type": "application/json"},
        json={"model": OPENAI_MODEL, "messages": messages,
              "temperature": 0.7, "max_tokens": max_tokens},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# ── Stub fallback (no API key) ────────────────────────────────────────────────
def _stub(prompt: str) -> str:
    """Minimal fallback when no LLM is configured."""
    return json.dumps({
        "summary": "An informative overview of the topic.",
        "key_points": ["Key insight 1", "Key insight 2", "Key insight 3"],
        "hooks": ["Did you know this topic is changing everything?"],
        "trending_aspects": ["Latest developments", "Future implications"],
        "target_audience": "general audience",
        "tone_suggestion": "educational",
        "estimated_duration": 6,
    })
