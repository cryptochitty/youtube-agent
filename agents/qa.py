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
    # Use hook + first section for a representative, self-contained excerpt
    hook_text   = script.get("hook", "")[:300]
    first_sec   = sections[0].get("content", "")[:300] if sections else ""
    review_text = f"Hook: {hook_text}\nFirst section: {first_sec}".strip()
    language    = state.get("language", "English")
    if review_text:
        try:
            llm_review = invoke_json(
                f'You are a YouTube content quality reviewer.\n'
                f'Topic: "{topic[:60]}"\n'
                f'Intended language: {language} — the script is CORRECTLY written in {language}, '
                f'this is intentional and must NOT be flagged as an issue.\n\n'
                f'Script sample:\n{review_text}\n\n'
                f'Rate only content quality. Return JSON: '
                f'{{"engagement_score": 0, "clarity_score": 0, "issues": [], "suggestions": []}} '
                f'Scores are integers 0-10. Only flag: factual errors, unclear arguments, '
                f'or very poor phrasing in {language}. '
                f'Do NOT flag: script length, language choice, use of {language}, excerpt being short.',
                max_tokens=300,
            )
        except Exception as e:
            logs.append(f"[QA] LLM review skipped: {e}")
            llm_review = {}
        if llm_review:
            eng = llm_review.get("engagement_score", 7)
            clr = llm_review.get("clarity_score", 7)
            # Blend: 60% structural checks, 40% LLM content review
            llm_score = int((eng + clr) / 20 * 100)
            score = int(score * 0.6 + llm_score * 0.4)
            # Filter out false-positive language complaints
            lang_lower = language.lower()
            raw_issues = llm_review.get("issues", [])
            filtered = [
                iss for iss in raw_issues
                if isinstance(iss, str) and not any(kw in iss.lower() for kw in (
                    "non-english", "not english", "not in english",
                    lang_lower, "language choice", "translation",
                    "excerpt", "too short", "too long",
                ))
            ]
            issues.extend(filtered)
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
