"""LangGraph shared state schema — passed between all agents."""
from typing import TypedDict, Optional, List, Dict, Any


class ScriptSection(TypedDict):
    title: str
    content: str
    visual_cue: str     # image/video generation prompt
    duration_hint: int  # seconds


class Scene(TypedDict):
    index: int
    section_title: str
    image_path: str
    audio_path: str
    duration: float
    subtitle: str


class VideoState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    topic:     str
    language:  str   # "English", "Tamil", etc.
    style:     str   # "Educational", "Cinematic", "Motivational"
    audience:  str   # "general", "students", "professionals"
    job_id:    str

    # ── Research ───────────────────────────────────────────────────────────
    research:  Dict[str, Any]   # {summary, key_points, hooks, trends, sources}

    # ── Script ─────────────────────────────────────────────────────────────
    script:    Dict[str, Any]   # {hook, intro, sections[], cta, full_script}

    # ── Voice ──────────────────────────────────────────────────────────────
    audio_files:     List[str]  # per-section mp3 paths
    total_duration:  float

    # ── Visuals ────────────────────────────────────────────────────────────
    image_files:  List[str]     # per-section image paths

    # ── Scenes (assembled) ────────────────────────────────────────────────
    scenes:  List[Scene]

    # ── Final outputs ──────────────────────────────────────────────────────
    video_path:      str
    thumbnail_path:  str
    metadata:        Dict[str, Any]  # {title, description, tags, thumbnail_text}

    # ── QA ─────────────────────────────────────────────────────────────────
    qa_report:  Dict[str, Any]  # {score, issues, approved}

    # ── Flow control ───────────────────────────────────────────────────────
    human_approved:   bool
    current_agent:    str
    errors:           List[str]
    logs:             List[str]
    status:           str   # queued|running|waiting_approval|done|failed
