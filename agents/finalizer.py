"""Finalizer Agent — packages all outputs, saves summary."""
import json, shutil
from pathlib import Path
from graph.state import VideoState
from config import OUTPUTS_DIR


def finalizer_agent(state: VideoState) -> VideoState:
    job_id = state.get("job_id", "default")
    logs   = state.get("logs", [])
    logs.append("[Finalizer] Packaging outputs...")

    # Ensure output directories exist
    for sub in ("videos", "scripts", "metadata"):
        (OUTPUTS_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Save script
    script_path = OUTPUTS_DIR / "scripts" / f"{job_id}.json"
    try:
        script_path.write_text(json.dumps(state.get("script", {}),
                                          indent=2, ensure_ascii=False))
    except Exception as e:
        logs.append(f"[Finalizer] Warning: could not save script: {e}")

    # Save metadata
    meta_path = OUTPUTS_DIR / "metadata" / f"{job_id}.json"
    try:
        meta_path.write_text(json.dumps(state.get("metadata", {}),
                                        indent=2, ensure_ascii=False))
    except Exception as e:
        logs.append(f"[Finalizer] Warning: could not save metadata: {e}")

    # Save final summary
    summary = {
        "job_id":          job_id,
        "topic":           state.get("topic"),
        "language":        state.get("language"),
        "status":          "completed",
        "video_path":      state.get("video_path"),
        "thumbnail_path":  state.get("thumbnail_path"),
        "script_path":     str(script_path),
        "metadata_path":   str(meta_path),
        "total_duration":  state.get("total_duration"),
        "qa_score":        state.get("qa_report", {}).get("score"),
        "title":           state.get("metadata", {}).get("title"),
        "description":     state.get("metadata", {}).get("description"),
        "tags":            state.get("metadata", {}).get("tags"),
    }

    summary_path = OUTPUTS_DIR / f"{job_id}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    logs.append(f"[Finalizer] All outputs saved.")
    logs.append(f"[Finalizer] Summary: {summary_path}")

    return {**state,
            "status":        "done",
            "current_agent": "done",
            "logs":          logs}
