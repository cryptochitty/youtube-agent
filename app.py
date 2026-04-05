"""
FastAPI server — REST API for the YouTube Agent pipeline.
Job state persisted to disk so Render restarts don't lose progress.
"""
import uuid, threading, json, traceback, os
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from config import OUTPUTS_DIR

app = FastAPI(title="YouTube AI Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

JOBS_DIR = OUTPUTS_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)


# ── Disk-persisted job state ──────────────────────────────────────────────────
def job_write(job_id: str, data: dict):
    path = JOBS_DIR / f"{job_id}.json"
    existing = job_read(job_id) or {}
    existing.update(data)
    path.write_text(json.dumps(existing, ensure_ascii=False))

def job_read(job_id: str) -> dict | None:
    path = JOBS_DIR / f"{job_id}.json"
    if path.exists():
        try: return json.loads(path.read_text())
        except Exception: pass
    return None


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
    job_write(job_id, {"status": "running", "logs": ["Pipeline started..."]})
    try:
        from graph.workflow import run_pipeline
        final = run_pipeline(
            topic    = req.topic,
            language = req.language,
            style    = req.style,
            audience = req.audience,
            mode     = "api",
            job_id   = job_id,
        )
        job_write(job_id, {
            "status":          final.get("status", "done"),
            "video_path":      final.get("video_path", ""),
            "thumbnail_path":  final.get("thumbnail_path", ""),
            "metadata":        final.get("metadata", {}),
            "qa_report":       final.get("qa_report", {}),
            "total_duration":  final.get("total_duration", 0),
            "logs":            final.get("logs", []),
            "errors":          final.get("errors", []),
        })
        # If not waiting for approval, mark done
        s = final.get("status")
        if s not in ("waiting_approval", "rejected"):
            job_write(job_id, {"status": "done"})
    except Exception as e:
        job_write(job_id, {
            "status": "failed",
            "errors": [str(e)],
            "logs":   [traceback.format_exc()[-2000:]],
        })


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.post("/generate")
async def generate(req: GenerateRequest, bg: BackgroundTasks):
    job_id = uuid.uuid4().hex[:8]
    job_write(job_id, {
        "job_id": job_id, "topic": req.topic, "language": req.language,
        "style": req.style, "status": "queued",
        "logs": [], "errors": [], "metadata": {}, "qa_report": {},
        "video_path": "", "thumbnail_path": "", "total_duration": 0,
    })
    bg.add_task(_run_job, job_id, req)
    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
async def status(job_id: str):
    job = job_read(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    vp = job.get("video_path", "")
    tp = job.get("thumbnail_path", "")
    return {
        "job_id":          job_id,
        "status":          job.get("status", "unknown"),
        "topic":           job.get("topic", ""),
        "logs":            job.get("logs", [])[-30:],
        "errors":          job.get("errors", []),
        "metadata":        job.get("metadata", {}),
        "qa_report":       job.get("qa_report", {}),
        "total_duration":  job.get("total_duration", 0),
        "video_ready":     bool(vp and Path(vp).exists()),
        "thumbnail_ready": bool(tp and Path(tp).exists()),
    }


@app.post("/approve/{job_id}")
async def approve(job_id: str, req: ApproveRequest, bg: BackgroundTasks):
    job = job_read(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not req.approved:
        job_write(job_id, {"status": "rejected"})
        return {"status": "rejected"}

    def _finalize():
        try:
            from agents.finalizer import finalizer_agent
            summary_path = OUTPUTS_DIR / f"{job_id}_summary.json"
            if summary_path.exists():
                state = json.loads(summary_path.read_text())
            else:
                state = job_read(job_id) or {}
            state["human_approved"] = True
            state["status"] = "running"
            final = finalizer_agent(state)
            job_write(job_id, {"status": "done", "logs": final.get("logs", [])})
        except Exception as e:
            job_write(job_id, {"status": "failed", "errors": [str(e)]})

    job_write(job_id, {"status": "finalizing"})
    bg.add_task(_finalize)
    return {"status": "finalizing"}


@app.get("/download/{job_id}/video")
async def dl_video(job_id: str):
    job = job_read(job_id) or {}
    path = job.get("video_path") or str(OUTPUTS_DIR / "videos" / f"{job_id}.mp4")
    if not Path(path).exists():
        raise HTTPException(404, "Video not ready")
    return FileResponse(path, media_type="video/mp4",
                        filename=f"youtube_{job_id}.mp4")

@app.get("/download/{job_id}/thumbnail")
async def dl_thumb(job_id: str):
    job = job_read(job_id) or {}
    path = job.get("thumbnail_path") or str(OUTPUTS_DIR / "thumbnails" / f"{job_id}.jpg")
    if not Path(path).exists():
        raise HTTPException(404, "Thumbnail not ready")
    return FileResponse(path, media_type="image/jpeg",
                        filename=f"thumbnail_{job_id}.jpg")

@app.get("/download/{job_id}/script")
async def dl_script(job_id: str):
    path = OUTPUTS_DIR / "scripts" / f"{job_id}.json"
    if not path.exists(): raise HTTPException(404, "Script not ready")
    return FileResponse(str(path), media_type="application/json",
                        filename=f"script_{job_id}.json")

@app.get("/download/{job_id}/metadata")
async def dl_meta(job_id: str):
    path = OUTPUTS_DIR / "metadata" / f"{job_id}.json"
    if not path.exists(): raise HTTPException(404, "Metadata not ready")
    return FileResponse(str(path), media_type="application/json",
                        filename=f"metadata_{job_id}.json")

@app.get("/")
async def root():
    return {"name": "YouTube AI Agent API", "version": "1.0.0",
            "docs": "/docs",
            "usage": {
                "generate": "POST /generate {'topic': 'Future of AI'}",
                "status":   "GET /status/{job_id}",
                "approve":  "POST /approve/{job_id} {'approved': true}",
                "download": "GET /download/{job_id}/video",
            }}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0",
                port=int(os.environ.get("PORT", 8000)), reload=False)
