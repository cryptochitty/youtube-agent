"""Script Writer Agent — generates full YouTube script with hook, sections, CTA."""
from graph.state import VideoState
from tools.llm_client import invoke_json


def script_writer_agent(state: VideoState) -> VideoState:
    topic    = state["topic"]
    research = state.get("research", {})
    style    = state.get("style", "Educational")
    language = state.get("language", "English")
    logs     = state.get("logs", [])
    logs.append("[Script] Writing script...")

    key_points = research.get("key_points", [])
    hooks      = research.get("hooks", [])
    tone       = research.get("tone_suggestion", "educational")
    duration   = research.get("estimated_duration", 8)

    prompt = f"""You are an expert YouTube scriptwriter.

Topic: "{topic}"
Style: {style}
Language: {language}
Target audience: {research.get('target_audience', 'general')}
Tone: {tone}
Target duration: {duration} minutes

Key research points:
{chr(10).join(f'- {p}' for p in key_points[:7])}

Opening hooks to choose from:
{chr(10).join(f'- {h}' for h in hooks[:3])}

Write a complete, engaging YouTube script. Return JSON with this structure:
{{
  "hook": "First 15 seconds — shocking fact or question that grabs attention immediately",
  "intro": "30-45 second introduction that sets up the video promise",
  "sections": [
    {{
      "title": "Section title",
      "content": "Full narration text for this section (2-4 sentences, conversational)",
      "visual_cue": "Description of visual to show (for image generation)",
      "key_takeaway": "One-line takeaway"
    }}
  ],
  "cta": "30-second call to action — subscribe, like, comment prompt",
  "total_sections": 4
}}

Requirements:
- Write in {language} language
- Use conversational, engaging language (not academic)
- Include storytelling and real examples
- Each section should be 30-60 seconds when spoken
- Create 4-5 main sections
- Hook must be dramatic and attention-grabbing
- CTA must feel genuine, not salesy"""

    script = invoke_json(prompt)

    if not script or not script.get("sections"):
        script = _fallback_script(topic, key_points, language)

    # Add hook and CTA as sections for uniform processing
    sections = []
    sections.append({
        "title": "Hook",
        "content": script.get("hook", f"Welcome! Today we explore {topic}."),
        "visual_cue": f"dramatic opener about {topic}",
        "key_takeaway": "Attention grabbed"
    })
    sections.append({
        "title": "Introduction",
        "content": script.get("intro", f"Let me tell you about {topic}."),
        "visual_cue": f"introduction to {topic}",
        "key_takeaway": "Context set"
    })
    sections.extend(script.get("sections", []))
    sections.append({
        "title": "Call to Action",
        "content": script.get("cta", "If you found this valuable, smash that like button!"),
        "visual_cue": "subscribe button, social media icons",
        "key_takeaway": "Audience engaged"
    })
    script["sections"] = sections

    # Build full script text
    script["full_script"] = "\n\n".join(
        f"[{s['title'].upper()}]\n{s['content']}" for s in sections
    )

    logs.append(f"[Script] Generated {len(sections)} sections.")

    return {**state,
            "script":        script,
            "current_agent": "voice",
            "logs":          logs}


def _fallback_script(topic: str, key_points: list, language: str) -> dict:
    points = key_points[:4] if key_points else [f"aspect of {topic}"]
    return {
        "hook": f"What if I told you that {topic} is about to change everything you know?",
        "intro": f"In this video, we're going to break down {topic} in a way that's clear, exciting, and packed with value.",
        "sections": [
            {
                "title": f"Understanding {topic}",
                "content": f"At its core, {topic} represents a fundamental shift. {points[0] if points else ''}",
                "visual_cue": f"diagram explaining {topic}",
                "key_takeaway": f"{topic} is transformative"
            },
            {
                "title": "Key Insights",
                "content": f"Here's what most people don't realize. {' '.join(points[1:3]) if len(points) > 1 else ''}",
                "visual_cue": f"infographic showing key facts about {topic}",
                "key_takeaway": "Surprising insights revealed"
            },
            {
                "title": "What This Means For You",
                "content": f"The implications of {topic} are massive. This affects you directly, and here's why.",
                "visual_cue": f"person benefiting from {topic}",
                "key_takeaway": "Personal impact clear"
            },
        ],
        "cta": "If this video opened your eyes, give it a thumbs up, subscribe, and drop a comment below!",
    }
