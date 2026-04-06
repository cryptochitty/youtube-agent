"""Video Editor Agent — assembles scenes into final MP4."""
import os
from graph.state import VideoState, Scene
from tools.video_tools import assemble_video, set_video_language
from config import OUTPUTS_DIR, get_palette


SCENE_COLORS = [
    (0, 210, 255), (255, 205, 50), (80, 255, 140),
    (255, 80, 110), (180, 120, 255), (255, 140, 60),
]


def editor_agent(state: VideoState) -> VideoState:
    script   = state.get("script", {})
    topic    = state.get("topic", "")
    job_id   = state.get("job_id", "default")
    logs     = state.get("logs", [])
    logs.append("[Editor] Assembling video...")

    sections = script.get("sections", [])
    palette  = get_palette(topic)
    set_video_language(state.get("language", "English"))

    # Build scene list for video assembly
    assembled_scenes = []
    for i, section in enumerate(sections):
        img_path   = section.get("image_path", "")
        audio_path = section.get("audio_path",  "")
        duration   = section.get("audio_duration", 5.0)

        # Skip sections with missing files
        if not img_path or not os.path.exists(img_path):
            logs.append(f"[Editor] Skip section {i+1}: missing image")
            continue

        assembled_scenes.append({
            "index":      i,
            "image_path": img_path,
            "audio_path": audio_path if (audio_path and os.path.exists(audio_path)) else "",
            "duration":   max(duration, 3.0),
            "subtitle":   section.get("content", ""),
            "title":      section.get("title", ""),
            "anim_data":  section.get("anim_data", {"type": "none"}),
        })

    if not assembled_scenes:
        err = "[Editor] No valid scenes to assemble!"
        logs.append(err)
        return {**state, "errors": state.get("errors", []) + [err],
                "status": "failed", "logs": logs}

    out_path = str(OUTPUTS_DIR / "videos" / f"{job_id}.mp4")
    accent_colors = [palette["accent"], palette["accent2"]] * 10

    total_scenes = len(assembled_scenes)

    def _progress(idx: int, msg: str):
        """Called by assemble_video after each scene clip is done."""
        entry = f"[Editor] Scene {idx+1}/{total_scenes} done — {msg}"
        logs.append(entry)
        # Persist log immediately so UI shows progress
        log_cb = state.get("_log_cb")
        if callable(log_cb):
            log_cb(entry)

    try:
        assemble_video(
            scenes        = assembled_scenes,
            out_path      = out_path,
            accent_colors = accent_colors,
            progress_cb   = _progress,
        )
        logs.append(f"[Editor] Video saved: {out_path}")
    except Exception as e:
        import traceback
        err = f"[Editor] Assembly failed: {e}"
        logs.append(err)
        logs.append(traceback.format_exc())
        return {**state, "errors": state.get("errors", []) + [err],
                "status": "failed", "logs": logs}

    # Build scenes list for state
    scene_objects: list = [
        Scene(
            index        = s["index"],
            section_title = s["title"],
            image_path   = s["image_path"],
            audio_path   = s["audio_path"],
            duration     = s["duration"],
            subtitle     = s["subtitle"][:100],
        )
        for s in assembled_scenes
    ]

    return {**state,
            "video_path":    out_path,
            "scenes":        scene_objects,
            "current_agent": "thumbnail",
            "logs":          logs}
