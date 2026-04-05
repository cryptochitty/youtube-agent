"""Visual Agent — generates scene images for each script section."""
import os
from graph.state import VideoState
from tools.image_client import generate_scene_image
from config import OUTPUTS_DIR


def visual_agent(state: VideoState) -> VideoState:
    script  = state.get("script", {})
    topic   = state.get("topic", "")
    job_id  = state.get("job_id", "default")
    logs    = state.get("logs", [])
    logs.append("[Visual] Generating scene images...")

    sections   = script.get("sections", [])
    img_dir    = OUTPUTS_DIR / "images" / job_id
    img_dir.mkdir(parents=True, exist_ok=True)

    image_files = []
    total = len(sections)

    for i, section in enumerate(sections):
        out_path = str(img_dir / f"scene_{i:02d}.jpg")
        try:
            generate_scene_image(
                section_index   = i,
                section_title   = section.get("title", ""),
                section_content = section.get("content", ""),
                topic           = topic,
                total_sections  = total,
                out_path        = out_path,
                visual_prompt   = section.get("visual_cue", ""),
            )
            section["image_path"] = out_path
            image_files.append(out_path)
            logs.append(f"[Visual] Scene {i+1}/{total} rendered.")
        except Exception as e:
            logs.append(f"[Visual] Error scene {i+1}: {e}")
            section["image_path"] = ""
            image_files.append("")

    state["script"]["sections"] = sections

    return {**state,
            "image_files":   image_files,
            "script":        state["script"],
            "current_agent": "editor",
            "logs":          logs}
