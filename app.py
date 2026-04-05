"""
FastAPI server — YouTube AI Agent pipeline.
Hybrid job state: in-memory (fast) + disk (survive restarts).
"""
import uuid, threading, json, traceback, os
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
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
class GenerateRequest(BaseModel):
    topic:    str
    language: str = "English"
    style:    str = "Educational"
    audience: str = "general"

class ApproveRequest(BaseModel):
    approved: bool = True


# ── Background worker ──────────────────────────────────────────────────────────
def _run_job(job_id: str, req: GenerateRequest):
    job_update(job_id, status="running")
    job_log(job_id, "🚀 Pipeline started...")

    try:
        # Import inside thread to catch import errors
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

        # Build initial state
        state = {
            "topic": req.topic, "language": req.language,
            "style": req.style, "audience": req.audience,
            "job_id": job_id, "_mode": "api",
            "research": {}, "script": {}, "audio_files": [],
            "total_duration": 0.0, "image_files": [], "scenes": [],
            "video_path": "", "thumbnail_path": "", "metadata": {},
            "qa_report": {}, "human_approved": False,
            "current_agent": "research", "errors": [], "logs": [], "status": "running",
        }

        # Run each agent with progress updates
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
            job_log(job_id, msg)
            job_update(job_id, current_agent=agent_name)
            state = agent_fn(state)

            # Sync logs from agent state
            new_logs = state.get("logs", [])
            if new_logs:
                job_update(job_id, logs=new_logs)

            # Check for failure
            if state.get("status") == "failed":
                job_update(job_id, status="failed",
                           errors=state.get("errors", []))
                return

            # HITL pause
            if state.get("status") == "waiting_approval":
                job_update(job_id,
                           status="waiting_approval",
                           qa_report=state.get("qa_report", {}),
                           metadata=state.get("metadata", {}),
                           total_duration=state.get("total_duration", 0),
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
        job_update(job_id, status="failed",
                   errors=[str(e)], logs=job_get(job_id).get("logs", []) + [tb[-1000:]])


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(_INDEX_HTML.read_text(encoding="utf-8"))


@app.post("/generate")
async def generate(req: GenerateRequest, bg: BackgroundTasks):
    try:
        if not req.topic.strip():
            raise HTTPException(400, "Topic cannot be empty")
        job_id = uuid.uuid4().hex[:8]
        job_update(job_id, job_id=job_id, topic=req.topic, language=req.language,
                   style=req.style, status="queued", logs=[], errors=[],
                   metadata={}, qa_report={}, video_path="", thumbnail_path="",
                   total_duration=0, video_ready=False, thumbnail_ready=False)
        bg.add_task(_run_job, job_id, req)
        return {"job_id": job_id, "status": "queued"}
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
            state = job.get("_state") or job
            state["human_approved"] = True
            state["status"] = "running"
            final = finalizer_agent(state)
            vp = final.get("video_path", "")
            tp = final.get("thumbnail_path", "")
            job_update(job_id, status="done",
                       video_path=vp, thumbnail_path=tp,
                       video_ready=bool(vp and Path(vp).exists()),
                       thumbnail_ready=bool(tp and Path(tp).exists()),
                       logs=final.get("logs", []))
        except Exception as e:
            job_update(job_id, status="failed", errors=[str(e)])

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
