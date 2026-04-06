"""
FastAPI server — YouTube AI Agent pipeline.
Hybrid job state: in-memory (fast) + disk (survive restarts).
Supports custom script / audio / images / video uploads.
"""
import uuid, threading, json, traceback, os, shutil
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from config import OUTPUTS_DIR, BASE_DIR

app = FastAPI(title="YouTube AI Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

JOBS_DIR    = OUTPUTS_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
_INDEX_HTML = BASE_DIR / "templates" / "index.html"

# In-memory store (primary — never wiped mid-run)
_JOBS: dict = {}


# ── Job state helpers ─────────────────────────────────────────────────────────
def job_update(job_id: str, **data):
    """Update in-memory + persist to disk."""
    if job_id not in _JOBS:
        _JOBS[job_id] = {}
    _JOBS[job_id].update(data)
    try:
        path = JOBS_DIR / f"{job_id}.json"
        # Don't save internal state (_state key) to disk
        safe = {k: v for k, v in _JOBS[job_id].items() if k != "_state"}
        path.write_text(json.dumps(safe, ensure_ascii=False, default=str))
    except Exception:
        pass

def job_get(job_id: str) -> dict | None:
    if job_id in _JOBS:
        return _JOBS[job_id]
    # Try disk fallback
    path = JOBS_DIR / f"{job_id}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            _JOBS[job_id] = data
            return data
        except Exception:
            pass
    return None

def job_log(job_id: str, msg: str):
    """Append a log line and persist."""
    job = job_get(job_id) or {}
    logs = job.get("logs", [])
    logs.append(msg)
    job_update(job_id, logs=logs)


# ── Request models ─────────────────────────────────────────────────────────────
class ApproveRequest(BaseModel):
    approved: bool = True


# ── Custom asset helpers ───────────────────────────────────────────────────────
_MAX_SECTION_CHARS = 600   # ~60 seconds of speech at average reading speed


def _split_into_chunks(text: str, max_chars: int = _MAX_SECTION_CHARS) -> list[str]:
    """Split long text into chunks ≤ max_chars, breaking at sentence boundaries."""
    import re
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, current = [], ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_chars:
            current = (current + " " + sent).strip()
        else:
            if current:
                chunks.append(current)
            # Single sentence longer than limit — hard split by words
            if len(sent) > max_chars:
                words = sent.split()
                current = ""
                for w in words:
                    if len(current) + len(w) + 1 <= max_chars:
                        current = (current + " " + w).strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = w
            else:
                current = sent
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _parse_uploaded_script(path: str) -> dict:
    """Parse uploaded script file (JSON or plain text) into pipeline script format."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "sections" in data:
            # Ensure each section has required fields, split long content
            expanded = []
            for i, s in enumerate(data["sections"]):
                s.setdefault("title",       s.get("title", f"Section {i+1}"))
                s.setdefault("content",     s.get("content", ""))
                s.setdefault("visual_cue",  "")
                s.setdefault("key_takeaway","")
                chunks = _split_into_chunks(s["content"])
                if len(chunks) == 1:
                    expanded.append(s)
                else:
                    for j, chunk in enumerate(chunks):
                        expanded.append({**s, "title": f"{s['title']} ({j+1})",
                                         "content": chunk,
                                         "key_takeaway": chunk[:60]})
            data["sections"] = expanded[:20]
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    # Plain text → split paragraphs into sections, chunk long ones
    paras = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    if not paras:
        paras = [p.strip() for p in text.splitlines() if p.strip()]
    sections = []
    for i, para in enumerate(paras[:20]):
        lines   = para.splitlines()
        title   = lines[0][:60] if len(lines) > 1 else f"Section {i+1}"
        content = para if len(lines) == 1 else "\n".join(lines[1:]).strip() or para
        for j, chunk in enumerate(_split_into_chunks(content)):
            label = title if j == 0 else f"{title} ({j+1})"
            sections.append({"title": label, "content": chunk,
                              "visual_cue": "", "key_takeaway": chunk[:60]})
            if len(sections) >= 20:
                break
        if len(sections) >= 20:
            break
    return {"sections": sections, "hook": "", "intro": "", "cta": ""}


def _audio_duration(path: str) -> float:
    """Get audio duration using ffprobe (bundled with imageio-ffmpeg)."""
    try:
        import subprocess, imageio_ffmpeg
        ffprobe = imageio_ffmpeg.get_ffmpeg_exe().replace("ffmpeg", "ffprobe")
        result  = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 5.0


def _apply_custom_audio(state: dict, audio_paths: list) -> dict:
    """Map uploaded audio files to script sections."""
    sections = state.get("script", {}).get("sections", [])
    audio_files = []
    total_dur   = 0.0
    for i, section in enumerate(sections):
        if i < len(audio_paths):
            ap  = audio_paths[i]
            dur = _audio_duration(ap)
            section["audio_path"]     = ap
            section["audio_duration"] = dur
            total_dur += dur
            audio_files.append(ap)
        else:
            section["audio_path"]     = ""
            section["audio_duration"] = 5.0
            audio_files.append("")
    state["script"]["sections"] = sections
    state["audio_files"]        = audio_files
    state["total_duration"]     = total_dur
    return state


def _apply_custom_images(state: dict, image_paths: list) -> dict:
    """Map uploaded images to script sections."""
    sections    = state.get("script", {}).get("sections", [])
    image_files = []
    for i, section in enumerate(sections):
        if i < len(image_paths):
            section["image_path"] = image_paths[i]
            image_files.append(image_paths[i])
        else:
            section["image_path"] = ""
            image_files.append("")
    state["script"]["sections"] = sections
    state["image_files"]        = image_files
    return state


# ── Background worker ──────────────────────────────────────────────────────────
def _run_job(job_id: str, topic: str, language: str, style: str, audience: str,
             custom: dict = None):
    job_update(job_id, status="running")
    job_log(job_id, "🚀 Pipeline started...")
    custom = custom or {}

    try:
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

        state = {
            "topic": topic, "language": language,
            "style": style, "audience": audience,
            "job_id": job_id, "_mode": "api",
            "research": {}, "script": {}, "audio_files": [],
            "total_duration": 0.0, "image_files": [], "scenes": [],
            "video_path": "", "thumbnail_path": "", "metadata": {},
            "qa_report": {}, "human_approved": False,
            "current_agent": "research", "errors": [], "logs": [], "status": "running",
        }

        # ── Apply custom assets & determine skips ─────────────────────────────
        skip = set()

        if custom.get("script_path"):
            job_log(job_id, "📄 Using uploaded script...")
            state["script"]   = _parse_uploaded_script(custom["script_path"])
            state["research"] = {"summary": f"Custom script for {topic}",
                                 "key_points": [], "hooks": [],
                                 "tone_suggestion": "educational", "estimated_duration": 8}
            skip.update({"research", "script_writer"})

            # Inject custom audio/images immediately (sections now known)
            if custom.get("audio_paths"):
                job_log(job_id, "🎵 Using uploaded audio...")
                state = _apply_custom_audio(state, custom["audio_paths"])
                skip.add("voice")
            if custom.get("image_paths"):
                job_log(job_id, "🖼️ Using uploaded images...")
                state = _apply_custom_images(state, custom["image_paths"])
                skip.add("visual")

        if custom.get("video_path"):
            job_log(job_id, "🎬 Using uploaded video...")
            out_vp = str(OUTPUTS_DIR / "videos" / f"{job_id}.mp4")
            shutil.copy(custom["video_path"], out_vp)
            state["video_path"] = out_vp
            skip.update({"research", "script_writer", "voice", "visual", "editor"})

        agents = [
            ("research",      research_agent,      "🔍 Researching topic..."),
            ("script_writer", script_writer_agent,  "✍️ Writing script..."),
            ("voice",         voice_agent,          "🎙️ Generating voiceover..."),
            ("visual",        visual_agent,         "🎨 Creating visuals..."),
            ("editor",        editor_agent,         "🎞️ Assembling video..."),
            ("thumbnail",     thumbnail_agent,      "🖼️ Making thumbnail..."),
            ("metadata",      metadata_agent,       "🧾 Writing SEO metadata..."),
            ("qa",            qa_agent,             "✅ Running QA check..."),
            ("hitl",          hitl_agent,           "👤 Requesting approval..."),
        ]

        for agent_name, agent_fn, msg in agents:
            if agent_name in skip:
                continue

            job_log(job_id, msg)
            job_update(job_id, current_agent=agent_name)
            state = agent_fn(state)

            # After script is generated, inject uploaded audio/images (if not yet done)
            if agent_name == "script_writer":
                if custom.get("audio_paths") and "voice" not in skip:
                    job_log(job_id, "🎵 Using uploaded audio...")
                    state = _apply_custom_audio(state, custom["audio_paths"])
                    skip.add("voice")
                if custom.get("image_paths") and "visual" not in skip:
                    job_log(job_id, "🖼️ Using uploaded images...")
                    state = _apply_custom_images(state, custom["image_paths"])
                    skip.add("visual")

            # Sync logs + key output paths from agent state to disk
            sync: dict = {"logs": state.get("logs", [])}
            if agent_name == "voice":
                sync["total_duration"] = state.get("total_duration", 0)
            if agent_name == "editor":
                vp = state.get("video_path", "")
                sync["video_path"]  = vp
                sync["video_ready"] = bool(vp and Path(vp).exists())
            if agent_name == "thumbnail":
                tp = state.get("thumbnail_path", "")
                sync["thumbnail_path"]  = tp
                sync["thumbnail_ready"] = bool(tp and Path(tp).exists())
            if agent_name == "metadata":
                sync["metadata"] = state.get("metadata", {})
            job_update(job_id, **sync)

            # Check for failure
            if state.get("status") == "failed":
                job_update(job_id, status="failed",
                           errors=state.get("errors", []))
                return

            # HITL pause — persist everything needed to survive a restart
            if state.get("status") == "waiting_approval":
                vp = state.get("video_path", "")
                tp = state.get("thumbnail_path", "")
                job_update(job_id,
                           status="waiting_approval",
                           qa_report=state.get("qa_report", {}),
                           metadata=state.get("metadata", {}),
                           total_duration=state.get("total_duration", 0),
                           video_path=vp,
                           thumbnail_path=tp,
                           video_ready=bool(vp and Path(vp).exists()),
                           thumbnail_ready=bool(tp and Path(tp).exists()),
                           _state=state)
                return

        # Run finalizer
        job_log(job_id, "📦 Finalizing outputs...")
        state = finalizer_agent(state)

        vp = state.get("video_path", "")
        tp = state.get("thumbnail_path", "")
        job_update(job_id,
                   status="done",
                   video_path=vp,
                   thumbnail_path=tp,
                   metadata=state.get("metadata", {}),
                   qa_report=state.get("qa_report", {}),
                   total_duration=state.get("total_duration", 0),
                   video_ready=bool(vp and Path(vp).exists()),
                   thumbnail_ready=bool(tp and Path(tp).exists()),
                   logs=state.get("logs", []))
        job_log(job_id, "✅ Done!")

    except Exception as e:
        tb = traceback.format_exc()
        existing_logs = (job_get(job_id) or {}).get("logs", [])
        job_update(job_id, status="failed",
                   errors=[str(e)], logs=existing_logs + [tb[-1000:]])


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(_INDEX_HTML.read_text(encoding="utf-8"))


@app.post("/generate")
async def generate(
    bg:           BackgroundTasks,
    topic:        str                  = Form(...),
    language:     str                  = Form("English"),
    style:        str                  = Form("Educational"),
    audience:     str                  = Form("general"),
    script_file:  Optional[UploadFile] = File(None),
    audio_files:  List[UploadFile]     = File(default=[]),
    image_files:  List[UploadFile]     = File(default=[]),
    video_file:   Optional[UploadFile] = File(None),
):
    try:
        if not topic.strip():
            raise HTTPException(400, "Topic cannot be empty")

        job_id   = uuid.uuid4().hex[:8]
        uploads  = OUTPUTS_DIR / "uploads" / job_id
        uploads.mkdir(parents=True, exist_ok=True)
        custom   = {}

        async def _save(upload: UploadFile, name: str) -> str:
            dest = str(uploads / name)
            with open(dest, "wb") as f:
                f.write(await upload.read())
            return dest

        if script_file and script_file.filename:
            suffix = Path(script_file.filename).suffix or ".txt"
            custom["script_path"] = await _save(script_file, f"script{suffix}")

        saved_audio = []
        for i, af in enumerate(audio_files or []):
            if af and af.filename:
                suffix = Path(af.filename).suffix or ".mp3"
                saved_audio.append(await _save(af, f"audio_{i:02d}{suffix}"))
        if saved_audio:
            custom["audio_paths"] = saved_audio

        saved_images = []
        for i, imgf in enumerate(image_files or []):
            if imgf and imgf.filename:
                suffix = Path(imgf.filename).suffix or ".jpg"
                saved_images.append(await _save(imgf, f"image_{i:02d}{suffix}"))
        if saved_images:
            custom["image_paths"] = saved_images

        if video_file and video_file.filename:
            custom["video_path"] = await _save(video_file, "video.mp4")

        job_update(job_id, topic=topic, language=language, style=style,
                   status="queued", logs=[], errors=[], metadata={}, qa_report={},
                   video_path="", thumbnail_path="", total_duration=0,
                   video_ready=False, thumbnail_ready=False,
                   custom_assets=list(custom.keys()))
        bg.add_task(_run_job, job_id, topic, language, style, audience, custom)
        return {"job_id": job_id, "status": "queued",
                "custom_assets": list(custom.keys())}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()[-500:]}


@app.get("/status/{job_id}")
async def status(job_id: str):
    job = job_get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id":          job_id,
        "status":          job.get("status", "unknown"),
        "topic":           job.get("topic", ""),
        "current_agent":   job.get("current_agent", ""),
        "logs":            job.get("logs", [])[-30:],
        "errors":          job.get("errors", []),
        "metadata":        job.get("metadata", {}),
        "qa_report":       job.get("qa_report", {}),
        "total_duration":  job.get("total_duration", 0),
        "video_ready":     job.get("video_ready", False),
        "thumbnail_ready": job.get("thumbnail_ready", False),
    }


@app.post("/approve/{job_id}")
async def approve(job_id: str, req: ApproveRequest, bg: BackgroundTasks):
    job = job_get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not req.approved:
        job_update(job_id, status="rejected")
        return {"status": "rejected"}

    def _finalize():
        try:
            from agents.finalizer import finalizer_agent
            # Prefer full in-memory state; fall back to reconstructing from disk data
            state = job.get("_state")
            if not state:
                state = {
                    "job_id":         job_id,
                    "topic":          job.get("topic", ""),
                    "language":       job.get("language", "English"),
                    "style":          job.get("style", "Educational"),
                    "audience":       job.get("audience", "general"),
                    "research":       job.get("research", {}),
                    "script":         job.get("script", {}),
                    "audio_files":    job.get("audio_files", []),
                    "total_duration": job.get("total_duration", 0),
                    "image_files":    job.get("image_files", []),
                    "scenes":         job.get("scenes", []),
                    "video_path":     job.get("video_path", ""),
                    "thumbnail_path": job.get("thumbnail_path", ""),
                    "metadata":       job.get("metadata", {}),
                    "qa_report":      job.get("qa_report", {}),
                    "errors":         job.get("errors", []),
                    "logs":           job.get("logs", []),
                    "status":         "running",
                    "current_agent":  "finalizer",
                    "human_approved": True,
                }
            state["human_approved"] = True
            state["status"] = "running"
            final = finalizer_agent(state)
            vp = final.get("video_path", "") or job.get("video_path", "")
            tp = final.get("thumbnail_path", "") or job.get("thumbnail_path", "")
            job_update(job_id, status="done",
                       video_path=vp, thumbnail_path=tp,
                       video_ready=bool(vp and Path(vp).exists()),
                       thumbnail_ready=bool(tp and Path(tp).exists()),
                       logs=final.get("logs", []))
        except Exception as e:
            job_update(job_id, status="failed", errors=[str(e), traceback.format_exc()[-500:]])

    job_update(job_id, status="finalizing")
    bg.add_task(_finalize)
    return {"status": "finalizing"}


@app.get("/download/{job_id}/video")
async def dl_video(job_id: str):
    job = job_get(job_id) or {}
    path = job.get("video_path") or str(OUTPUTS_DIR / "videos" / f"{job_id}.mp4")
    if not Path(path).exists():
        raise HTTPException(404, "Video not ready")
    return FileResponse(path, media_type="video/mp4",
                        filename=f"youtube_{job_id}.mp4")

@app.get("/download/{job_id}/thumbnail")
async def dl_thumb(job_id: str):
    job = job_get(job_id) or {}
    path = job.get("thumbnail_path") or str(OUTPUTS_DIR / "thumbnails" / f"{job_id}.jpg")
    if not Path(path).exists():
        raise HTTPException(404, "Thumbnail not ready")
    return FileResponse(path, media_type="image/jpeg",
                        filename=f"thumbnail_{job_id}.jpg")

@app.get("/download/{job_id}/script")
async def dl_script(job_id: str):
    path = OUTPUTS_DIR / "scripts" / f"{job_id}.json"
    if not path.exists(): raise HTTPException(404, "Not ready")
    return FileResponse(str(path), media_type="application/json",
                        filename=f"script_{job_id}.json")

@app.get("/download/{job_id}/metadata")
async def dl_meta(job_id: str):
    path = OUTPUTS_DIR / "metadata" / f"{job_id}.json"
    if not path.exists(): raise HTTPException(404, "Not ready")
    return FileResponse(str(path), media_type="application/json",
                        filename=f"metadata_{job_id}.json")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0",
                port=int(os.environ.get("PORT", 8000)), reload=False)
