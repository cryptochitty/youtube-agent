"""
LangGraph multi-agent workflow.

Flow:
  research → script_writer → voice → visual → editor
          → thumbnail → metadata → qa → hitl → finalizer → END
"""
import uuid
from typing import Literal
from langgraph.graph import StateGraph, END
from graph.state import VideoState
from agents.research     import research_agent
from agents.script_writer import script_writer_agent
from agents.voice         import voice_agent
from agents.visual        import visual_agent
from agents.editor        import editor_agent
from agents.thumbnail     import thumbnail_agent
from agents.metadata      import metadata_agent
from agents.qa            import qa_agent
from agents.hitl          import hitl_agent
from agents.finalizer      import finalizer_agent


# ── Conditional edges ─────────────────────────────────────────────────────────
def route_after_editor(state: VideoState) -> Literal["thumbnail", "__end__"]:
    if state.get("status") == "failed":
        return "__end__"
    return "thumbnail"

def route_after_hitl(state: VideoState) -> Literal["finalizer", "__end__"]:
    status = state.get("status")
    if status in ("rejected", "waiting_approval"):
        return "__end__"   # UI will re-invoke finalizer after approval
    return "finalizer"

def route_after_qa(state: VideoState) -> Literal["hitl", "__end__"]:
    # Auto-approve if score ≥ 85 (skip HITL in fully automated mode)
    qa  = state.get("qa_report", {})
    mode = state.get("_mode", "api")
    if mode == "auto" and qa.get("score", 0) >= 85:
        return "__end__"   # Will be handled by finalizer separately
    return "hitl"


# ── Build graph ───────────────────────────────────────────────────────────────
def build_workflow() -> StateGraph:
    g = StateGraph(VideoState)

    # Register nodes
    g.add_node("research",      research_agent)
    g.add_node("script_writer", script_writer_agent)
    g.add_node("voice",         voice_agent)
    g.add_node("visual",        visual_agent)
    g.add_node("editor",        editor_agent)
    g.add_node("thumbnail",     thumbnail_agent)
    g.add_node("metadata",      metadata_agent)
    g.add_node("qa",            qa_agent)
    g.add_node("hitl",          hitl_agent)
    g.add_node("finalizer",     finalizer_agent)

    # Entry point
    g.set_entry_point("research")

    # Linear edges
    g.add_edge("research",      "script_writer")
    g.add_edge("script_writer", "voice")
    g.add_edge("voice",         "visual")

    # Conditional: editor → thumbnail (or END if failed)
    g.add_conditional_edges("visual",  lambda s: "editor",   {"editor": "editor"})
    g.add_conditional_edges("editor",  route_after_editor,
                             {"thumbnail": "thumbnail", "__end__": END})

    g.add_edge("thumbnail", "metadata")

    # Conditional: qa → hitl or end
    g.add_edge("metadata", "qa")
    g.add_conditional_edges("qa", route_after_qa,
                             {"hitl": "hitl", "__end__": END})
    g.add_conditional_edges("hitl", route_after_hitl,
                             {"finalizer": "finalizer", "__end__": END})
    g.add_edge("finalizer", END)

    return g.compile()


# ── Public runner ─────────────────────────────────────────────────────────────
def run_pipeline(
    topic:    str,
    language: str = "English",
    style:    str = "Educational",
    audience: str = "general",
    mode:     str = "api",   # "cli" | "api" | "auto"
    job_id:   str = None,
) -> VideoState:
    """Run the full pipeline synchronously. Returns final state."""
    if not job_id:
        job_id = uuid.uuid4().hex[:8]

    initial: VideoState = {
        "topic":           topic,
        "language":        language,
        "style":           style,
        "audience":        audience,
        "job_id":          job_id,
        "_mode":           mode,
        "research":        {},
        "script":          {},
        "audio_files":     [],
        "total_duration":  0.0,
        "image_files":     [],
        "scenes":          [],
        "video_path":      "",
        "thumbnail_path":  "",
        "metadata":        {},
        "qa_report":       {},
        "human_approved":  False,
        "current_agent":   "research",
        "errors":          [],
        "logs":            [],
        "status":          "running",
    }

    app = build_workflow()
    final_state = app.invoke(initial)
    return final_state


def stream_pipeline(topic: str, language: str = "English",
                    style: str = "Educational", audience: str = "general",
                    job_id: str = None):
    """Generator that yields state snapshots as the pipeline runs."""
    if not job_id:
        job_id = uuid.uuid4().hex[:8]

    initial: VideoState = {
        "topic": topic, "language": language,
        "style": style, "audience": audience,
        "job_id": job_id, "_mode": "api",
        "research": {}, "script": {}, "audio_files": [],
        "total_duration": 0.0, "image_files": [], "scenes": [],
        "video_path": "", "thumbnail_path": "", "metadata": {},
        "qa_report": {}, "human_approved": False,
        "current_agent": "research", "errors": [],
        "logs": [], "status": "running",
    }

    app = build_workflow()
    for step in app.stream(initial):
        yield step
