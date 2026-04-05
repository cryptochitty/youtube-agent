"""
Simple sequential pipeline — no LangGraph/LangChain dependency.
Saves ~300MB RAM. Each agent is called in order.
"""
import uuid
from graph.state import VideoState


def run_pipeline(
    topic:    str,
    language: str = "English",
    style:    str = "Educational",
    audience: str = "general",
    mode:     str = "api",
    job_id:   str = None,
) -> VideoState:
    """Run all agents sequentially. Returns final state."""
    if not job_id:
        job_id = uuid.uuid4().hex[:8]

    state: VideoState = {
        "topic": topic, "language": language,
        "style": style, "audience": audience,
        "job_id": job_id, "_mode": mode,
        "research": {}, "script": {}, "audio_files": [],
        "total_duration": 0.0, "image_files": [], "scenes": [],
        "video_path": "", "thumbnail_path": "", "metadata": {},
        "qa_report": {}, "human_approved": False,
        "current_agent": "research", "errors": [], "logs": [],
        "status": "running",
    }

    # Import agents lazily to reduce startup memory
    from agents.research      import research_agent
    from agents.script_writer import script_writer_agent
    from agents.voice         import voice_agent
    from agents.visual        import visual_agent
    from agents.editor        import editor_agent
    from agents.thumbnail     import thumbnail_agent
    from agents.metadata      import metadata_agent
    from agents.qa            import qa_agent
    from agents.hitl          import hitl_agent
    from agents.finalizer     import finalizer_agent

    pipeline = [
        research_agent, script_writer_agent, voice_agent,
        visual_agent, editor_agent, thumbnail_agent,
        metadata_agent, qa_agent, hitl_agent, finalizer_agent,
    ]

    for agent_fn in pipeline:
        state = agent_fn(state)
        # Stop on failure or human approval pause
        if state.get("status") in ("failed", "waiting_approval", "rejected"):
            break

    return state
