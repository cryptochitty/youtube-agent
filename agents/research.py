"""Research Agent — collects topic info, trends, hooks via web search + LLM."""
from graph.state import VideoState
from tools.llm_client import invoke_json
from tools.search_client import search_web, search_trends


def research_agent(state: VideoState) -> VideoState:
    topic    = state["topic"]
    language = state.get("language", "English")
    logs     = state.get("logs", [])
    logs.append("[Research] Starting research...")

    # 1. Web search
    snippets = search_trends(topic)
    web_ctx  = "\n\n".join(snippets[:6]) if snippets else "No external data available."

    # 2. LLM analysis
    prompt = f"""You are a YouTube research expert.

Topic: "{topic}"
Language: {language}
Audience: {state.get('audience', 'general')}

Web search context:
{web_ctx}

Analyze this topic and return a JSON object with these exact keys:
{{
  "summary": "2-3 sentence overview of the topic",
  "key_points": ["5-7 important facts or insights about this topic"],
  "hooks": ["3 attention-grabbing opening hooks for YouTube (first 5 seconds)"],
  "trending_aspects": ["3-4 trending angles for 2025-2026"],
  "target_audience": "describe who would watch this",
  "tone_suggestion": "educational|motivational|storytelling|documentary",
  "estimated_duration": 8
}}"""

    research = invoke_json(prompt, max_tokens=1024)

    # Fallback if LLM fails
    if not research:
        research = {
            "summary": f"An exploration of {topic} and its impact.",
            "key_points": [f"Key insight about {topic}"],
            "hooks": [f"Did you know that {topic} is changing everything?"],
            "trending_aspects": [f"The future of {topic}"],
            "target_audience": "general audience",
            "tone_suggestion": "educational",
            "estimated_duration": 8,
        }

    logs.append(f"[Research] Found {len(research.get('key_points',[]))} key points.")

    return {**state,
            "research":      research,
            "current_agent": "script_writer",
            "logs":          logs,
            "status":        "running"}
