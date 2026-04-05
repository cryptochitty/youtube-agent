"""Thumbnail Agent — generates eye-catching YouTube thumbnail."""
from graph.state import VideoState
from tools.image_client import generate_thumbnail
from tools.llm_client import invoke_json
from config import OUTPUTS_DIR


def thumbnail_agent(state: VideoState) -> VideoState:
    topic    = state.get("topic", "")
    script   = state.get("script", {})
    metadata = state.get("metadata", {})
    job_id   = state.get("job_id", "default")
    logs     = state.get("logs", [])
    logs.append("[Thumbnail] Generating thumbnail...")

    # Get or generate a catchy thumbnail title
    thumb_title = metadata.get("title", topic)
    if len(thumb_title) > 40:
        # Ask LLM for a shorter, punchier thumbnail text
        result = invoke_json(
            f'Generate a short (max 4 words, ALL CAPS) thumbnail text for a YouTube video about "{topic}". '
            'Return JSON: {{"thumbnail_text": "YOUR TEXT"}}'
        )
        thumb_title = result.get("thumbnail_text", topic.upper()[:30])

    out_path = str(OUTPUTS_DIR / "thumbnails" / f"{job_id}.jpg")

    try:
        generate_thumbnail(topic, thumb_title, out_path)
        logs.append(f"[Thumbnail] Saved: {out_path}")
    except Exception as e:
        logs.append(f"[Thumbnail] Error: {e}")
        out_path = ""

    return {**state,
            "thumbnail_path": out_path,
            "current_agent":  "metadata",
            "logs":           logs}
