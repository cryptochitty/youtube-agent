"""QA Agent — reviews script quality, audio-video sync, engagement."""
import os
from graph.state import VideoState
from tools.llm_client import invoke_json


def qa_agent(state: VideoState) -> VideoState:
    topic    = state.get("topic", "")
    script   = state.get("script", {})
    metadata = state.get("metadata", {})
    logs     = state.get("logs", [])
    logs.append("[QA] Running quality checks...")

    sections    = script.get("sections", [])
    video_path  = state.get("video_path", "")
    thumb_path  = state.get("thumbnail_path", "")
    issues      = []
    score       = 100

    # ── Structural checks ─────────────────────────────────────────────────
    if len(sections) < 3:
        issues.append("Too few sections (minimum 3 recommended)")
        score -= 15

    if not script.get("hook"):
        issues.append("Missing hook")
        score -= 10

    for i, sec in enumerate(sections):
        if not sec.get("content", "").strip():
            issues.append(f"Section {i+1} has empty content")
            score -= 5
        if not os.path.exists(sec.get("audio_path", "")):
            issues.append(f"Section {i+1} missing audio file")
            score -= 8
        if not os.path.exists(sec.get("image_path", "")):
            issues.append(f"Section {i+1} missing image file")
            score -= 8

    # ── Video file check ──────────────────────────────────────────────────
    if not video_path or not os.path.exists(video_path):
        issues.append("Final video file missing!")
        score -= 30
    else:
        size_mb = os.path.getsize(video_path) / (1024*1024)
        if size_mb < 0.1:
            issues.append(f"Video file suspiciously small ({size_mb:.2f}MB)")
            score -= 20

    # ── Metadata check ────────────────────────────────────────────────────
    if not metadata.get("title"):
        issues.append("Missing video title")
        score -= 5
    if not metadata.get("tags"):
        issues.append("Missing tags")
        score -= 5
    if not thumb_path or not os.path.exists(thumb_path):
        issues.append("Missing thumbnail")
        score -= 5

    # ── LLM content review ────────────────────────────────────────────────
    full_script = script.get("full_script", "")[:500]
    if full_script:
        try:
            llm_review = invoke_json(
                f'Review this YouTube script. Topic: "{topic[:100]}"\n\n'
                f'Excerpt:\n{full_script}\n\n'
                'Return JSON: {"engagement_score": 0-10, "clarity_score": 0-10, '
                '"issues": ["list of problems"], "suggestions": ["improvements"]}',
                max_tokens=256,
            )
        except Exception as e:
            logs.append(f"[QA] LLM review skipped: {e}")
            llm_review = {}
        if llm_review:
            eng = llm_review.get("engagement_score", 7)
            clr = llm_review.get("clarity_score", 7)
            score = min(score, int((eng + clr) / 20 * 100))
            issues.extend(llm_review.get("issues", []))
            logs.append(f"[QA] LLM scores — Engagement: {eng}/10, Clarity: {clr}/10")

    score = max(0, min(100, score))
    qa_report = {
        "score":    score,
        "issues":   issues,
        "approved": score >= 60,
        "grade":    "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "F",
    }

    logs.append(f"[QA] Score: {score}/100 — Grade: {qa_report['grade']}")
    if issues:
        logs.append(f"[QA] Issues: {'; '.join(issues[:3])}")

    return {**state,
            "qa_report":     qa_report,
            "current_agent": "hitl",
            "logs":          logs}
