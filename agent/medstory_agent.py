"""
MedExplain Agent — Multimodal Patient Education Video Generator
"""

import asyncio
import base64
import json
import os
import subprocess
import tempfile
import typing
from pathlib import Path

import vertexai  # type: ignore
from google.cloud import texttospeech  # type: ignore
from vertexai.generative_models import GenerativeModel  # type: ignore
from vertexai.preview.vision_models import ImageGenerationModel  # type: ignore

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "medexplain-demo")
LOCATION   = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# Basic in-memory cache for generated images based on the prompt description.
# In a production app, this would be a Redis or DB cache.
image_cache: typing.Dict[str, str] = {}

vertexai.init(project=PROJECT_ID, location=LOCATION)


async def generate_scene_script(procedure_name: str) -> dict:
    model = GenerativeModel("gemini-2.0-flash-001")
    prompt = f"""
You are a compassionate medical educator creating patient-friendly content.
Educational use ONLY — never give medical advice or diagnoses.

Create a short explainer script for patients about: **{procedure_name}**

Return ONLY valid JSON with this exact structure:
{{
  "title": "Understanding {procedure_name}",
  "summary": "One sentence overview for patients",
  "scenes": [
    {{
      "scene_number": 1,
      "title": "Short scene title",
      "narration": "2-3 sentences of simple, warm, reassuring narration.",
      "image_prompt": "Medical diagram description: detailed, educational, clean style"
    }}
  ]
}}

Requirements:
- Exactly 5 scenes
- Scene flow: Introduction → What it is → Why it's done → What happens → Recovery
- Narration: 8th grade reading level, warm and reassuring
- NEVER give specific medical advice or diagnoses
"""
    response = await model.generate_content_async(prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# Healthcare color palettes per scene type
SCENE_PALETTES = [
    {"bg": (10, 22, 48),     "accent": (0, 188, 212),   "card": (20, 40, 80),    "text": (255,255,255)},
    {"bg": (5, 60, 45),     "accent": (56, 210, 180),   "card": (10, 90, 70),   "text": (255,255,255)},
    {"bg": (30, 15, 60),    "accent": (149, 117, 220),  "card": (50, 30, 90),   "text": (255,255,255)},
    {"bg": (8, 38, 60),     "accent": (41, 182, 246),   "card": (15, 60, 88),   "text": (255,255,255)},
    {"bg": (40, 10, 20),    "accent": (240, 98,  146),  "card": (70, 20, 40),   "text": (255,255,255)},
]

MEDICAL_ICONS = ["⚕", "🫀", "🫁", "🧬", "💊", "🩺", "🔬", "🩻", "🩹", "🧪"]


def _wrap_text(text: str, max_chars: int) -> typing.List[str]:
    """Simple word-wrap helper."""
    words = text.split()
    lines: typing.List[str] = []
    line: typing.List[str] = []
    count = 0
    for word in words:
        if count + len(word) + 1 > max_chars and line:
            lines.append(" ".join(line))
            line, count = [word], len(word)
        else:
            line.append(word)
            count += len(word) + 1
    if line:
        lines.append(" ".join(line))
    return lines


def create_placeholder_image(
    scene_number: int,
    title: str,
    narration: str,
    output_path: Path,
    total_scenes: int = 5,
) -> None:
    """Create a rich, fully-filled, healthcare-themed slide image."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter  # type: ignore

    W, H = 1920, 1080
    pal = SCENE_PALETTES[(scene_number - 1) % len(SCENE_PALETTES)]
    bg, accent, card_col, txt_col = pal["bg"], pal["accent"], pal["card"], pal["text"]

    img = Image.new("RGB", (W, H), bg)  # type: ignore
    draw = ImageDraw.Draw(img, "RGBA")  # type: ignore

    # ── Gradient overlay (simulate depth) ──────────────────────────────────
    for y in range(H):
        alpha = int(40 * (y / H))
        draw.line([(0, y), (W, y)], fill=(*bg, alpha))  # type: ignore

    # ── Left decorative bar ─────────────────────────────────────────────────
    draw.rectangle([0, 0, 8, H], fill=(*accent, 255))  # type: ignore

    # ── Background grid dots (subtle) ──────────────────────────────────────
    dot_col = (*accent, 18)  # type: ignore
    for gx in range(0, W, 60):
        for gy in range(0, H, 60):
            draw.ellipse([gx-2, gy-2, gx+2, gy+2], fill=dot_col)  # type: ignore

    # ── Header bar ─────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, 110], fill=(*card_col, 220))  # type: ignore
    draw.rectangle([0, 108, W, 114], fill=(*accent, 255))  # type: ignore

    # ── Cross-platform font finder ────────────────────────────────────────
    def _find_font(size: int) -> "ImageFont.FreeTypeFont":  # type: ignore
        """Return the best available TrueType font at the requested pt size."""
        candidates = [
            # Windows
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            # Linux / Debian / Ubuntu
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
            # macOS
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)  # type: ignore
            except Exception:
                continue
        # Hard fallback: PIL default (will be small but at least visible)
        return ImageFont.load_default()  # type: ignore

    font_lg = _find_font(72)
    font_md = _find_font(48)
    font_sm = _find_font(34)
    font_xs = _find_font(28)

    # ── Header: branding + step label ──────────────────────────────────────
    draw.text((40, 24), "MedStory", font=font_sm, fill=(*accent, 255))  # type: ignore
    step_label = f"Step {scene_number} of {total_scenes}"
    draw.text((W - 320, 30), step_label, font=font_xs, fill=(*txt_col, 180))  # type: ignore

    # ── Scene progress dots ─────────────────────────────────────────────────
    dot_x = W // 2 - (total_scenes * 28) // 2
    for i in range(total_scenes):
        cx = dot_x + i * 28
        if i + 1 == scene_number:
            draw.ellipse([cx - 9, 46, cx + 9, 64], fill=(*accent, 255))  # type: ignore
        elif i + 1 < scene_number:
            draw.ellipse([cx - 7, 48, cx + 7, 62], fill=(*accent, 140))  # type: ignore
        else:
            draw.ellipse([cx - 7, 48, cx + 7, 62], fill=(*txt_col, 50))  # type: ignore

    # ── Large central medical icon ──────────────────────────────────────────
    icon = MEDICAL_ICONS[(scene_number - 1) % len(MEDICAL_ICONS)]
    # Draw emoji via a slightly blurred background circle
    cx, cy = W // 2, H // 2 - 40
    r = 170
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # type: ignore
    ov_draw = ImageDraw.Draw(overlay)  # type: ignore
    ov_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*card_col, 160))  # type: ignore
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"), (0, 0))  # type: ignore
    draw = ImageDraw.Draw(img, "RGBA")  # type: ignore
    draw.ellipse([cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4], outline=(*accent, 200), width=3)  # type: ignore

    # ── Large central icon label (text-based, works on any font) ──────────
    # Map each scene to a short text label drawn large inside the circle
    icon_labels = ["Rx", "♥", "✚", "⚕", "★"]
    icon_text = icon_labels[(scene_number - 1) % len(icon_labels)]
    try:
        icon_font_big = _find_font(160)  # type: ignore
        draw.text((cx, cy), icon_text, font=icon_font_big, fill=(*accent, 230), anchor="mm")  # type: ignore
    except Exception:
        draw.text((cx - 30, cy - 30), icon_text, font=font_lg, fill=(*accent, 200))  # type: ignore

    # ── Title area ─────────────────────────────────────────────────────────
    title_wrapped = _wrap_text(title[:80], 38)  # type: ignore
    ty = 140
    for line in title_wrapped[:2]:  # type: ignore
        draw.text((W // 2, ty), line, font=font_md, fill=(*txt_col, 255), anchor="mm")  # type: ignore
        ty += 56

    # ── Bottom caption card ─────────────────────────────────────────────────
    card_y = H - 220
    draw.rectangle([80, card_y, W - 80, H - 40], fill=(*card_col, 210), outline=(*accent, 120), width=2)  # type: ignore
    narr_lines = _wrap_text(narration[:240], 80)  # type: ignore
    ny = card_y + 24
    for line in narr_lines[:3]:  # type: ignore
        draw.text((W // 2, ny), line, font=font_xs, fill=(*txt_col, 220), anchor="mm")  # type: ignore
        ny += 38

    # ── Decorative corner accents ───────────────────────────────────────────
    for x0, y0, x1, y1 in [(0,0,60,4),(0,0,4,60),(W-60,0,W,4),(W-4,0,W,60)]:
        draw.rectangle([x0, y0, x1, y1], fill=(*accent, 180))  # type: ignore
    for x0, y0, x1, y1 in [(0,H-4,60,H),(0,H-60,4,H),(W-60,H-4,W,H),(W-4,H-60,W,H)]:
        draw.rectangle([x0, y0, x1, y1], fill=(*accent, 180))  # type: ignore

    img.save(str(output_path))


async def generate_scene_images(scenes: list) -> list:
    output_dir = Path(tempfile.mkdtemp(prefix="medstory_images_"))
    
    try:
        imagen = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")
    except Exception as e:
        print(f"[WARN] Could not load Imagen model: {e}. Using placeholders.")
        imagen = None

    async def _process_scene_image(scene: dict) -> dict:
        img_path = output_dir / f"scene_{scene['scene_number']:02d}.png"
        success = False

        if imagen:
            prompt = (
                f"Medical education illustration: {scene['image_prompt']}. "
                "Clean vector-style diagram, pastel colors, professional medical "
                "textbook style, no text overlays, educational infographic aesthetic."
            )
            # Check cache first
            if scene['image_prompt'] in image_cache:
                print(f"  ⚡ Using cached image for scene {scene['scene_number']}")
                with open(img_path, "wb") as f:
                    f.write(base64.b64decode(image_cache[scene['image_prompt']]))
                success = True
            else:
                try:
                    def _generate():  # type: ignore
                        return imagen.generate_images(  # type: ignore
                            prompt=prompt,
                            number_of_images=1,
                            aspect_ratio="16:9",
                            safety_filter_level="block_some",
                            person_generation="dont_allow",
                        )
                    images = await asyncio.to_thread(_generate)  # type: ignore
                    def _save(img: "Any") -> None:  # type: ignore
                        img.save(str(img_path))
                    await asyncio.to_thread(_save, images[0])  # type: ignore
                    success = True
                    print(f"  ✅ Image generated for scene {scene['scene_number']}")
                except Exception as e:
                    print(f"  [WARN] Imagen failed for scene {scene['scene_number']}: {e}")

        if not success:
            print(f"  Using placeholder for scene {scene['scene_number']}")
            create_placeholder_image(
                scene["scene_number"],
                scene["title"],
                scene.get("narration", ""),
                img_path,
                total_scenes=5,
            )

        def _read_b64(*args: typing.Any, **kwargs: typing.Any) -> str:
            with open(img_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        
        b64 = await asyncio.to_thread(_read_b64)  # type: ignore
        scene_copy = dict(scene)
        scene_copy["image_base64"] = b64
        scene_copy["image_path"] = str(img_path)
        
        # Save to cache on success
        if success and scene['image_prompt'] not in image_cache:
            image_cache[scene['image_prompt']] = b64

        return scene_copy

    tasks = [_process_scene_image(scene) for scene in scenes]
    enriched = await asyncio.gather(*tasks)
    return list(enriched)


async def generate_narration(scenes: list) -> list:
    client = texttospeech.TextToSpeechClient()
    output_dir = Path(tempfile.mkdtemp(prefix="medstory_audio_"))

    # Try Journey-F first, fall back to Neural2-F if it fails
    voice_configs = [
        {"name": "en-US-Journey-F", "pitch": None},
        {"name": "en-US-Neural2-F", "pitch": -1.0},
        {"name": "en-US-Standard-F", "pitch": None},
    ]

    async def _process_scene_audio(scene: dict) -> dict:
        synthesis_input = texttospeech.SynthesisInput(text=scene["narration"])
        audio_path = output_dir / f"scene_{scene['scene_number']:02d}.mp3"
        success = False

        for vc in voice_configs:
            try:
                voice = texttospeech.VoiceSelectionParams(
                    language_code="en-US",
                    name=vc["name"],
                    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
                )
                audio_config_params = {
                    "audio_encoding": texttospeech.AudioEncoding.MP3,
                    "speaking_rate": 0.9,
                }
                if vc["pitch"] is not None:
                    audio_config_params["pitch"] = vc["pitch"]

                audio_config = texttospeech.AudioConfig(**audio_config_params)
                def _synth():  # type: ignore
                    return client.synthesize_speech(
                        request={"input": synthesis_input, "voice": voice, "audio_config": audio_config}
                    )
                response = await asyncio.to_thread(_synth)  # type: ignore
                def _write_audio() -> None:
                    with open(audio_path, "wb") as f:
                        f.write(response.audio_content)  # type: ignore
                await asyncio.to_thread(_write_audio)  # type: ignore
                print(f"  ✅ Narration generated for scene {scene['scene_number']} using {vc['name']}")
                success = True
                break
            except Exception as e:
                print(f"  [WARN] Voice {vc['name']} failed: {e}")

        if not success:
            print(f"  [ERROR] All voices failed for scene {scene['scene_number']}")
            return {**scene, "audio_base64": "", "audio_path": ""}

        def _read_b64(*args: typing.Any, **kwargs: typing.Any) -> str:
            with open(audio_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        b64 = await asyncio.to_thread(_read_b64)  # type: ignore
        scene_copy = dict(scene)
        scene_copy["audio_base64"] = b64
        scene_copy["audio_path"] = str(audio_path)
        return scene_copy

    tasks = [_process_scene_audio(scene) for scene in scenes]
    enriched = await asyncio.gather(*tasks)
    return list(enriched)


async def assemble_video(title: str, scenes: list) -> dict:
    output_dir = Path(tempfile.mkdtemp(prefix="medstory_video_"))
    final_video = output_dir / "explainer.mp4"
    FADE = 0.6   # crossfade duration in seconds

    # ── Phase 1: build one clip per scene with Ken Burns + fade-in/out ──────
    scene_clips: typing.List[Path] = []

    for scene in scenes:
        if not scene.get("image_path") or not scene.get("audio_path"):
            print(f"  [SKIP] Scene {scene.get('scene_number')} missing image or audio")
            continue

        clip_path = output_dir / f"clip_{scene['scene_number']:02d}.mp4"

        def _ffprobe(audio_path: str = scene["audio_path"]) -> "subprocess.CompletedProcess[str]":
            return subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, text=True
            )
        probe = await asyncio.to_thread(_ffprobe)  # type: ignore
        duration = float(probe.stdout.strip() or "10")
        clip_dur = duration + 0.8   # small tail so audio doesn't cut

        # Ken Burns: slow pan+zoom from 110% down to 100% over clip duration
        zoom_speed = 0.0006          # pixels-per-frame zoom rate
        fps = 25
        total_frames = int(clip_dur * fps)

        # Compute zoom so image starts at 110% and ends at 100%
        zoom_expr = (
            f"min(1.10,1.10-{zoom_speed:.6f}*(on-1))"
        )
        ken_burns = (
            f"scale=8000:-1,"
            f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={total_frames}:s=1920x1080:fps={fps},"
            f"scale=1920:1080,setsar=1"
        )
        vf = (
            f"{ken_burns},"
            f"fade=t=in:st=0:d={FADE},"
            f"fade=t=out:st={max(0.0, clip_dur - FADE):.3f}:d={FADE}"
        )

        def _build_clip(
            img_path: str = scene["image_path"],
            audio_path: str = scene["audio_path"],
            out: str = str(clip_path),
            dur: float = clip_dur,
            vf_str: str = vf,
        ) -> None:
            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1",
                "-framerate", str(fps),
                "-i", img_path,
                "-i", audio_path,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-t", str(dur),
                "-vf", vf_str,
                out,
            ], check=True, capture_output=True)

        await asyncio.to_thread(_build_clip)  # type: ignore
        scene_clips.append(clip_path)
        print(f"  ✅ Clip assembled for scene {scene['scene_number']}")

    if not scene_clips:
        return {"video_path": "", "video_base64": ""}

    # ── Phase 2: join clips with xfade crossfade transitions ─────────────────
    def _join_clips(
        clips: typing.List[Path] = scene_clips,
        out: str = str(final_video),
    ) -> None:
        if len(clips) == 1:
            # Single scene — just copy it
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(clips[0]), "-c", "copy", out],
                check=True, capture_output=True,
            )
            return

        # Build a filtergraph that xfades consecutive clips
        # First, probe each clip's duration
        durations: typing.List[float] = []
        for clip in clips:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(clip)],
                capture_output=True, text=True
            )
            durations.append(float(r.stdout.strip() or "10"))

        n = len(clips)
        inputs: typing.List[str] = []
        for clip in clips:
            inputs += ["-i", str(clip)]

        # Build xfade filter chain
        filter_parts: typing.List[str] = []
        audio_parts:  typing.List[str] = []
        offset = 0.0

        for i in range(n):
            filter_parts.append(f"[{i}:v]")
            audio_parts.append(f"[{i}:a]")

        # Video xfade chain
        vchain = "[0:v]"
        for i in range(1, n):
            offset += durations[i - 1] - FADE
            next_in = f"[{i}:v]"
            out_label = f"[xv{i}]" if i < n - 1 else "[vout]"
            filter_parts.append(
                f"{vchain}{next_in}xfade=transition=fade:duration={FADE}:offset={offset:.3f}{out_label}"
            )
            vchain = f"[xv{i}]"

        # Audio concat chain (no gap audio)
        audio_inputs = "".join(f"[{i}:a]" for i in range(n))
        filter_parts.append(f"{audio_inputs}concat=n={n}:v=0:a=1[aout]")

        filtergraph = ";".join(filter_parts)

        subprocess.run(
            ["ffmpeg", "-y"] + inputs + [
                "-filter_complex", filtergraph,
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                out,
            ],
            check=True, capture_output=True,
        )

    await asyncio.to_thread(_join_clips)  # type: ignore

    def _read_b64(*args: typing.Any, **kwargs: typing.Any) -> str:
        with open(final_video, "rb") as f:
            return base64.b64encode(f.read()).decode()

    video_b64 = await asyncio.to_thread(_read_b64)  # type: ignore
    print(f"  ✅ Final video: {final_video}")
    return {"video_path": str(final_video), "video_base64": video_b64}


async def run_pipeline(procedure: str) -> dict:
    print(f"\n🩺 MedStory pipeline starting for: {procedure}\n")

    print("[1/4] Generating scene script...")
    script = await generate_scene_script(procedure)
    print(f"  ✅ Script: '{script['title']}' ({len(script['scenes'])} scenes)\n")

    print("[2/4] Generating scene images...")
    scenes_with_images = await generate_scene_images(script["scenes"])
    print()

    print("[3/4] Generating narration audio...")
    scenes_full = await generate_narration(scenes_with_images)
    print()

    print("[4/4] Assembling video...")
    video_result = await assemble_video(script["title"], scenes_full)
    print()

    return {
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
        "video_path": video_result.get("video_path", ""),
        "disclaimer": "For patient education only. Not medical advice. Always consult your healthcare provider.",
    }


if __name__ == "__main__":
    import sys
    procedure = sys.argv[1] if len(sys.argv) > 1 else "Appendectomy"
    result = asyncio.run(run_pipeline(procedure))
    print(f"✅ Pipeline complete!")
    print(f"   Title   : {result['title']}")
    print(f"   Summary : {result['summary']}")
    print(f"   Video   : {result['video_path']}")
    print(f"   Scenes  : {len(result['scenes'])}")
