"""Voice Agent — generates TTS audio for each script section."""
import os
from graph.state import VideoState
from tools.tts_client import synthesize
from config import OUTPUTS_DIR


def voice_agent(state: VideoState) -> VideoState:
    script   = state.get("script", {})
    language = state.get("language", "English")
    job_id   = state.get("job_id", "default")
    logs     = state.get("logs", [])
    logs.append("[Voice] Generating voiceover...")

    sections    = script.get("sections", [])
    audio_files = []
    total_dur   = 0.0
    audio_dir   = OUTPUTS_DIR / "audio" / job_id
    audio_dir.mkdir(parents=True, exist_ok=True)

    for i, section in enumerate(sections):
        text = section.get("content", "").strip()[:600]   # hard cap: ~60s of speech
        if not text:
            continue
        out_path = str(audio_dir / f"section_{i:02d}.mp3")
        try:
            dur = synthesize(text, language, out_path)
            section["audio_path"]    = out_path
            section["audio_duration"] = dur
            total_dur += dur
            audio_files.append(out_path)
            logs.append(f"[Voice] Section {i+1}/{len(sections)}: {dur:.1f}s")
        except Exception as e:
            logs.append(f"[Voice] Error section {i+1}: {e}")
            section["audio_path"]    = ""
            section["audio_duration"] = 5.0
            audio_files.append("")

    state["script"]["sections"] = sections

    logs.append(f"[Voice] Total duration: {total_dur:.1f}s ({total_dur/60:.1f} min)")

    return {**state,
            "audio_files":   audio_files,
            "total_duration": total_dur,
            "script":        state["script"],
            "current_agent": "visual",
            "logs":          logs}
