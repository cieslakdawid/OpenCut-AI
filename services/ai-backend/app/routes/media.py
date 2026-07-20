"""Media transcoding routes.

Converts video whose codec the browser cannot decode (e.g. Apple ProRes
'apch', DNxHD) into H.264 video + AAC audio in an MP4 container, which every
browser's WebCodecs decoder supports. The web app calls this automatically
when `videoTrack.canDecode()` returns false on import.

FFmpeg is already installed in the ai-backend image.
"""

import asyncio
import logging
import os
import shutil
import tempfile
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])

# Read the upload from the network in 8 MB chunks so large ProRes files are
# streamed to disk instead of buffered entirely in memory.
_CHUNK = 8 * 1024 * 1024

# Transcode to widely-decodable H.264 (8-bit 4:2:0) + AAC. `veryfast` keeps
# CPU-only encoding reasonable; faststart moves the moov atom to the front so
# the browser can start reading immediately.
_FFMPEG_ARGS = [
    "-c:v", "libx264",
    "-preset", "veryfast",
    "-pix_fmt", "yuv420p",
    "-crf", "23",
    "-c:a", "aac",
    "-b:a", "192k",
    "-movflags", "+faststart",
]

# Cap the ffmpeg run so a pathological file can't pin a CPU forever.
_TRANSCODE_TIMEOUT_S = 60 * 30  # 30 minutes


def _cleanup(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


@router.post("/transcode")
async def transcode(file: UploadFile = File(...)) -> FileResponse:
    """Transcode an uploaded video to H.264/AAC MP4 and stream it back."""
    workdir = tempfile.mkdtemp(prefix="transcode_")
    # Preserve the original extension so ffmpeg can sniff the input format.
    _, ext = os.path.splitext(file.filename or "")
    in_path = os.path.join(workdir, f"input{ext or '.bin'}")
    out_path = os.path.join(workdir, "output.mp4")

    # Stream the upload to disk in chunks.
    try:
        with open(in_path, "wb") as f:
            while chunk := await file.read(_CHUNK):
                f.write(chunk)
    except Exception:
        _cleanup(workdir)
        logger.exception("Failed to buffer upload for transcode")
        raise HTTPException(status_code=500, detail="Failed to read uploaded file.")

    if os.path.getsize(in_path) == 0:
        _cleanup(workdir)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    cmd = ["ffmpeg", "-y", "-i", in_path, *_FFMPEG_ARGS, out_path]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_TRANSCODE_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            proc.kill()
            _cleanup(workdir)
            raise HTTPException(
                status_code=504,
                detail="Transcode timed out. The file may be too large.",
            )
    except HTTPException:
        raise
    except Exception:
        _cleanup(workdir)
        logger.exception("ffmpeg failed to start")
        raise HTTPException(status_code=500, detail="Transcode process failed to start.")

    if proc.returncode != 0 or not os.path.exists(out_path):
        detail = (stderr or b"").decode("utf-8", "replace")[-600:]
        _cleanup(workdir)
        logger.error("ffmpeg transcode failed: %s", detail)
        raise HTTPException(
            status_code=422,
            detail="Could not transcode this file — its format may be unsupported.",
        )

    base = os.path.splitext(os.path.basename(file.filename or "video"))[0]
    download_name = f"{base or 'video'}_{uuid.uuid4().hex[:8]}.mp4"

    # FileResponse streams the result; BackgroundTask removes the temp dir
    # only after the response has been fully sent.
    return FileResponse(
        path=out_path,
        media_type="video/mp4",
        filename=download_name,
        background=BackgroundTask(_cleanup, workdir),
    )
