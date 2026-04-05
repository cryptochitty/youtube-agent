"""Metadata Agent — generates SEO-optimized title, description, tags."""
import json
from graph.state import VideoState
from tools.llm_client import invoke_json
from config import OUTPUTS_DIR


def metadata_agent(state: VideoState) -> VideoState:
    topic    = state.get("topic", "")
    script   = state.get("script", {})
    research = state.get("research", {})
    job_id   = state.get("job_id", "default")
    logs     = state.get("logs", [])
    logs.append("[Metadata] Generating SEO metadata...")

    hook     = script.get("hook", "")
    sections = script.get("sections", [])
    section_titles = [s.get("title","") for s in sections]
    duration = state.get("total_duration", 300)

    prompt = f"""You are a YouTube SEO expert.

Topic: "{topic}"
Script hook: "{hook}"
Sections: {section_titles}
Video duration: {int(duration//60)} minutes {int(duration%60)} seconds
Research summary: {research.get('summary','')}

Generate SEO-optimized YouTube metadata. Return JSON:
{{
  "title": "Clickbait but accurate title, max 70 chars, with numbers/power words",
  "description": "Full YouTube description, 200-300 words. Include: hook, what viewers learn, timestamps, call to action, hashtags",
  "tags": ["tag1", "tag2", ...20 relevant tags],
  "thumbnail_text": "4-5 word punch for thumbnail (ALL CAPS)",
  "category": "Education|Science & Technology|Howto & Style",
  "language": "{state.get('language','English')}"
}}

Title requirements: include year (2025/2026), numbers, emotional triggers
Description requirements: first 2 lines must be compelling (shown in search)"""

    metadata = invoke_json(prompt, max_tokens=1024)

    if not metadata or not metadata.get("title"):
        metadata = _fallback_metadata(topic, section_titles, duration)

    # Save metadata JSON
    meta_path = OUTPUTS_DIR / "metadata" / f"{job_id}.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    logs.append(f"[Metadata] Saved: {meta_path}")

    return {**state,
            "metadata":      metadata,
            "current_agent": "qa",
            "logs":          logs}


def _fallback_metadata(topic: str, sections: list, duration: float) -> dict:
    import datetime
    year = datetime.datetime.now().year
    return {
        "title": f"{topic} Explained | Complete Guide {year}",
        "description": (
            f"🚀 In this video, we explore everything about {topic}.\n\n"
            f"What you'll learn:\n" +
            "\n".join(f"✅ {s}" for s in sections[:5]) +
            f"\n\n⏱️ Duration: {int(duration//60)}:{int(duration%60):02d}\n\n"
            f"🔔 Subscribe for more content!\n\n"
            f"#{topic.replace(' ','')} #AI #Technology #Education"
        ),
        "tags": [topic, "AI", "technology", "education", "explained",
                 "tutorial", "guide", "2025", "future", "innovation"],
        "thumbnail_text": topic.upper()[:25],
        "category": "Education",
    }
