"""
MedStory API — FastAPI backend
"""
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
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
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id].update({"current_step": "Generating scene script...", "progress": 10})
        script = await generate_scene_script(procedure)

        jobs[job_id].update({"current_step": "Creating medical diagrams...", "progress": 30})
        scenes_with_images = await generate_scene_images(script["scenes"])

        jobs[job_id].update({"current_step": "Synthesizing narration...", "progress": 60})
        scenes_full = await generate_narration(scenes_with_images)

        jobs[job_id].update({"current_step": "Assembling video...", "progress": 85})
        video_result = await assemble_video(script["title"], scenes_full)

        jobs[job_id].update({
            "status": "complete", "progress": 100, "current_step": "Done!",
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
                "video_base64": video_result.get("video_base64", ""),
                "disclaimer": "For patient education only. Not medical advice.",
            },
        })
    except Exception as e:
        jobs[job_id].update({"status": "error", "progress": 0, "current_step": "Error", "error": str(e)})


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
