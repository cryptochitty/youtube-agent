"""
FastAPI server — REST API for the YouTube Agent pipeline.

Endpoints:
  POST /generate        — start a job
  GET  /status/{job_id} — poll job status + logs
  GET  /download/{job_id}/video
  GET  /download/{job_id}/thumbnail
  GET  /download/{job_id}/script
  GET  /download/{job_id}/metadata
  POST /approve/{job_id} — human approval (HITL)
"""
import uuid, threading, json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from config import OUTPUTS_DIR

app = FastAPI(title="YouTube AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# In-memory job store
JOBS: dict = {}


# ── Request models ────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    topic:    str
    language: str = "English"
    style:    str = "Educational"
    audience: str = "general"


class ApproveRequest(BaseModel):
    approved: bool = True


# ── Background worker ─────────────────────────────────────────────────────────
def _run_job(job_id: str, request: GenerateRequest):
    JOBS[job_id]["status"] = "running"
    JOBS[job_id]["logs"].append("Pipeline started...")
    try:
        from graph.workflow import run_pipeline
        final = run_pipeline(
            topic    = request.topic,
            language = request.language,
            style    = request.style,
            audience = request.audience,
            mode     = "api",
            job_id   = job_id,
        )
        JOBS[job_id].update({
            "status":         final.get("status", "done"),
            "video_path":     final.get("video_path", ""),
            "thumbnail_path": final.get("thumbnail_path", ""),
            "metadata":       final.get("metadata", {}),
            "qa_report":      final.get("qa_report", {}),
            "total_duration": final.get("total_duration", 0),
            "logs":           final.get("logs", []),
            "errors":         final.get("errors", []),
            "_state":         final,
        })
        if final.get("status") != "waiting_approval":
            JOBS[job_id]["status"] = "done"
    except Exception as e:
        import traceback
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["errors"].append(str(e))
        JOBS[job_id]["logs"].append(traceback.format_exc())


# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/generate")
async def generate(req: GenerateRequest, bg: BackgroundTasks):
    """Start a video generation job. Returns job_id immediately."""
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {
        "job_id":   job_id,
        "topic":    req.topic,
        "language": req.language,
        "style":    req.style,
        "status":   "queued",
        "logs":     [],
        "errors":   [],
        "metadata": {},
        "qa_report": {},
        "video_path": "",
        "thumbnail_path": "",
        "total_duration": 0,
    }
    bg.add_task(_run_job, job_id, req)
    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
async def status(job_id: str):
    """Poll job status and progress logs."""
    job = JOBS.get(job_id)
    if not job:
        # Try loading from disk
        summary_path = OUTPUTS_DIR / f"{job_id}_summary.json"
        if summary_path.exists():
            return json.loads(summary_path.read_text())
        raise HTTPException(404, "Job not found")

    return {
        "job_id":         job_id,
        "status":         job["status"],
        "topic":          job["topic"],
        "logs":           job["logs"][-20:],   # last 20 log lines
        "errors":         job["errors"],
        "metadata":       job.get("metadata", {}),
        "qa_report":      job.get("qa_report", {}),
        "total_duration": job.get("total_duration", 0),
        "video_ready":    bool(job.get("video_path") and
                               Path(job["video_path"]).exists()),
        "thumbnail_ready": bool(job.get("thumbnail_path") and
                                Path(job["thumbnail_path"]).exists()),
    }


@app.post("/approve/{job_id}")
async def approve(job_id: str, req: ApproveRequest, bg: BackgroundTasks):
    """Human approval endpoint for HITL step."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "waiting_approval":
        raise HTTPException(400, f"Job is in status '{job['status']}', not waiting for approval")

    if not req.approved:
        JOBS[job_id]["status"] = "rejected"
        return {"status": "rejected"}

    # Resume pipeline from finalizer
    def _finalize():
        try:
            from agents.finalizer import finalizer_agent
            state = JOBS[job_id].get("_state", {})
            state["human_approved"] = True
            state["status"] = "running"
            final = finalizer_agent(state)
            JOBS[job_id].update({
                "status": "done",
                "logs":   final.get("logs", []),
            })
        except Exception as e:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["errors"].append(str(e))

    bg.add_task(_finalize)
    JOBS[job_id]["status"] = "finalizing"
    return {"status": "finalizing"}


@app.get("/download/{job_id}/video")
async def download_video(job_id: str):
    job = JOBS.get(job_id) or {}
    path = job.get("video_path") or str(OUTPUTS_DIR / "videos" / f"{job_id}.mp4")
    if not Path(path).exists():
        raise HTTPException(404, "Video not ready")
    return FileResponse(path, media_type="video/mp4",
                        filename=f"youtube_{job_id}.mp4")


@app.get("/download/{job_id}/thumbnail")
async def download_thumbnail(job_id: str):
    job = JOBS.get(job_id) or {}
    path = job.get("thumbnail_path") or str(OUTPUTS_DIR / "thumbnails" / f"{job_id}.jpg")
    if not Path(path).exists():
        raise HTTPException(404, "Thumbnail not ready")
    return FileResponse(path, media_type="image/jpeg",
                        filename=f"thumbnail_{job_id}.jpg")


@app.get("/download/{job_id}/script")
async def download_script(job_id: str):
    path = OUTPUTS_DIR / "scripts" / f"{job_id}.json"
    if not path.exists():
        raise HTTPException(404, "Script not ready")
    return FileResponse(str(path), media_type="application/json",
                        filename=f"script_{job_id}.json")


@app.get("/download/{job_id}/metadata")
async def download_metadata(job_id: str):
    path = OUTPUTS_DIR / "metadata" / f"{job_id}.json"
    if not path.exists():
        raise HTTPException(404, "Metadata not ready")
    return FileResponse(str(path), media_type="application/json",
                        filename=f"metadata_{job_id}.json")


@app.get("/")
async def root():
    return {
        "name": "YouTube AI Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "usage": {
            "generate": "POST /generate {'topic': 'Future of AI'}",
            "status":   "GET /status/{job_id}",
            "approve":  "POST /approve/{job_id} {'approved': true}",
            "download": "GET /download/{job_id}/video",
        }
    }


if __name__ == "__main__":
    import os, uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
