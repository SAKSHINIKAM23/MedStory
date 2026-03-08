"""
MedStory API — FastAPI backend
"""
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

jobs: dict = {}


class GenerateRequest(BaseModel):
    procedure: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    current_step: str
    result: Optional[dict] = None
    error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("MedStory API starting...")
    yield

app = FastAPI(title="MedStory API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def run_generation_job(job_id: str, procedure: str):
    from agent.medstory_agent import (
        generate_scene_script, generate_scene_images,
        generate_narration, assemble_video,
    )

    def update(step: str, pct: int) -> None:
        jobs[job_id].update({"current_step": step, "progress": pct})

    try:
        jobs[job_id]["status"] = "processing"
        update("Generating scene script with AI...", 5)
        script = await generate_scene_script(procedure)
        total = len(script["scenes"])

        # ── Images: progress 10 → 50 per scene ─────────────
        update(f"Creating visuals for scene 1 of {total}...", 10)
        def img_callback(scene_num: int) -> None:
            pct = 10 + int((scene_num / total) * 40)
            update(f"Creating visuals for scene {scene_num} of {total}...", pct)

        scenes_with_images = await generate_scene_images(script["scenes"], img_callback)

        # ── Audio: progress 50 → 80 per scene ─────────────
        update(f"Synthesising narration for scene 1 of {total}...", 50)
        def audio_callback(scene_num: int) -> None:
            pct = 50 + int((scene_num / total) * 30)
            update(f"Synthesising narration for scene {scene_num} of {total}...", pct)

        scenes_full = await generate_narration(scenes_with_images, audio_callback)

        # ── Video assembly: 80 → 95 ───────────────────────
        def video_callback(scene_num: int) -> None:
            pct = 80 + int((scene_num / total) * 15)
            update(f"Encoding clip {scene_num} of {total}...", pct)

        update("Assembling final video...", 80)
        video_result = await assemble_video(script["title"], scenes_full, video_callback)

        update("Finalising...", 98)
        jobs[job_id].update({
            "status": "complete", "progress": 100, "current_step": "Done!",
            "_video_path": video_result.get("video_path", ""),
            "result": {
                "procedure": procedure,
                "title": script["title"],
                "summary": script["summary"],
                "scenes": [
                    {
                        "scene_number": s["scene_number"],
                        "title": s["title"],
                        "narration": s["narration"],
                        "image_base64": s.get("image_base64", ""),
                        "audio_base64": s.get("audio_base64", ""),
                    }
                    for s in scenes_full
                ],
                "video_url": f"/jobs/{job_id}/video",
                "disclaimer": "For patient education only. Not medical advice.",
            },
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        jobs[job_id].update({"status": "error", "progress": 0,
                             "current_step": "Error", "error": str(e)})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "MedStory API"}

@app.post("/generate", response_model=JobStatus)
async def generate_video(req: GenerateRequest, background_tasks: BackgroundTasks):
    if not req.procedure.strip():
        raise HTTPException(status_code=400, detail="Procedure name required.")
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"job_id": job_id, "status": "queued", "progress": 0,
                    "current_step": "Queued...", "result": None, "error": None}
    background_tasks.add_task(run_generation_job, job_id, req.procedure.strip())
    return JobStatus(**jobs[job_id])

@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatus(**jobs[job_id])

@app.get("/jobs/{job_id}/video")
async def stream_video(job_id: str, request: Request):
    """Stream the generated MP4 with byte-range support for proper browser seeking."""
    import os
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = jobs[job_id]
    if job.get("status") != "complete":
        raise HTTPException(status_code=425, detail="Video not ready yet.")
    video_path = job.get("_video_path", "")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found on server.")

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get("range")

    def _iter_file(start: int, end: int):
        with open(video_path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            chunk_size = 1024 * 256  # 256 KB chunks
            while remaining > 0:
                data = f.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    if range_header:
        # Partial content (seek support)
        try:
            range_val = range_header.replace("bytes=", "")
            start_str, end_str = range_val.split("-")
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
        except Exception:
            raise HTTPException(status_code=416, detail="Invalid Range header.")
        end = min(end, file_size - 1)
        content_length = end - start + 1
        return StreamingResponse(
            _iter_file(start, end),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Cache-Control": "no-cache",
            },
        )
    else:
        # Full file
        return StreamingResponse(
            _iter_file(0, file_size - 1),
            status_code=200,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Cache-Control": "no-cache",
            },
        )


@app.get("/procedures/suggestions")
async def suggest_procedures():
    return {"suggestions": ["Appendectomy", "Knee Replacement", "Cataract Surgery",
            "Colonoscopy", "Hip Replacement", "Tonsillectomy", "MRI Scan"]}

@app.get("/")
async def root():
    return {
        "service": "MedStory API",
        "status": "running",
        "docs": "/docs",
        "endpoints": ["/health", "/generate", "/jobs/{job_id}", "/procedures/suggestions"]
    }
