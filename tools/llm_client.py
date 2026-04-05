"""Multi-provider LLM client — Groq → Ollama → fallback."""
import json, re
from config import LLM_PROVIDER, GROQ_API_KEY, GROQ_MODEL, OLLAMA_URL, OLLAMA_MODEL


def get_llm():
    """Return a LangChain LLM object based on configured provider."""
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(api_key=GROQ_API_KEY, model_name=GROQ_MODEL,
                            temperature=0.7, max_tokens=4096)
        except Exception as e:
            print(f"[LLM] Groq failed: {e}, falling back to Ollama")

    if LLM_PROVIDER in ("ollama", "groq"):
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(base_url=OLLAMA_URL, model=OLLAMA_MODEL,
                              temperature=0.7)
        except Exception as e:
            print(f"[LLM] Ollama failed: {e}")

    if LLM_PROVIDER == "openai":
        from config import OPENAI_KEY, OPENAI_MODEL
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(api_key=OPENAI_KEY, model=OPENAI_MODEL, temperature=0.7)

    raise RuntimeError(
        "No LLM available. Set GROQ_API_KEY in .env (free at console.groq.com) "
        "or run Ollama locally."
    )


def invoke_llm(prompt: str, system: str = "") -> str:
    """Single call — returns string response."""
    from langchain_core.messages import HumanMessage, SystemMessage
    llm = get_llm()
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    response = llm.invoke(messages)
    return response.content.strip()


def invoke_json(prompt: str, system: str = "", retries: int = 2) -> dict:
    """Call LLM and parse JSON response — retries on parse failure."""
    for attempt in range(retries + 1):
        raw = invoke_llm(prompt + "\n\nRespond ONLY with valid JSON, no markdown fences.",
                         system)
        # Strip markdown fences if present
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON object/array
            m = re.search(r'\{[\s\S]+\}|\[[\s\S]+\]', raw)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
            if attempt == retries:
                print(f"[LLM] JSON parse failed after {retries+1} attempts. Raw:\n{raw[:300]}")
                return {}
    return {}
