"""Human-in-the-Loop Agent — presents summary and waits for approval."""
from graph.state import VideoState


def hitl_agent(state: VideoState) -> VideoState:
    """
    In API/UI mode: just sets status to 'waiting_approval'.
    In CLI mode: prompts user interactively.
    """
    logs      = state.get("logs", [])
    qa_report = state.get("qa_report", {})
    metadata  = state.get("metadata", {})
    mode      = state.get("_mode", "api")   # "cli" or "api"

    logs.append("[HITL] Requesting human approval...")

    summary = _build_summary(state)
    logs.append(summary)

    if mode == "cli":
        # Interactive CLI approval
        print("\n" + "="*60)
        print(summary)
        print("="*60)
        answer = input("\n✅ Approve and finalize? [y/N]: ").strip().lower()
        approved = answer in ("y", "yes")
        if not approved:
            logs.append("[HITL] User rejected — stopping pipeline.")
            return {**state, "human_approved": False, "status": "rejected",
                    "current_agent": "done", "logs": logs}
    else:
        # API/UI mode: set status to waiting, approval comes via separate endpoint
        return {**state,
                "human_approved": False,
                "status":         "waiting_approval",
                "current_agent":  "finalizer",
                "logs":           logs}

    logs.append("[HITL] Approved! Finalizing...")
    return {**state,
            "human_approved": True,
            "status":         "running",
            "current_agent":  "finalizer",
            "logs":           logs}


def _build_summary(state: VideoState) -> str:
    qa       = state.get("qa_report", {})
    metadata = state.get("metadata", {})
    sections = state.get("script", {}).get("sections", [])
    dur      = state.get("total_duration", 0)

    return (
        f"📹 VIDEO GENERATION SUMMARY\n"
        f"Topic:     {state.get('topic','')}\n"
        f"Language:  {state.get('language','English')}\n"
        f"Title:     {metadata.get('title','')}\n"
        f"Sections:  {len(sections)}\n"
        f"Duration:  {int(dur//60)}:{int(dur%60):02d}\n"
        f"QA Score:  {qa.get('score',0)}/100 (Grade: {qa.get('grade','?')})\n"
        f"Video:     {state.get('video_path','')}\n"
        f"Thumbnail: {state.get('thumbnail_path','')}\n"
        + (f"Issues:    {'; '.join(qa.get('issues',[])[:3])}\n" if qa.get('issues') else "")
    )
