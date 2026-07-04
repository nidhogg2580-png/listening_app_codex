from __future__ import annotations

import base64
import mimetypes
import re
import subprocess
from pathlib import Path
from typing import BinaryIO


SUPPORTED_VIDEO_TYPES = ("mp4", "mov", "avi", "mkv")
BROWSER_READY_EXTENSIONS = {".mp4", ".m4v"}


def safe_filename(filename: str) -> str:
    path = Path(filename)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._") or "video"
    suffix = path.suffix.lower()
    return f"{stem}{suffix}"


def unique_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / safe_filename(filename)
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        numbered = directory / f"{stem}_{counter}{suffix}"
        if not numbered.exists():
            return numbered
        counter += 1


def save_uploaded_file(uploaded_file: BinaryIO, upload_dir: Path) -> Path:
    target_path = unique_path(upload_dir, uploaded_file.name)
    with target_path.open("wb") as output:
        output.write(uploaded_file.getbuffer())
    return target_path


def convert_to_browser_mp4(input_path: Path) -> tuple[Path, str | None]:
    if input_path.suffix.lower() in BROWSER_READY_EXTENSIONS:
        return input_path, None

    try:
        import imageio_ffmpeg
    except ImportError:
        return input_path, "未安装 FFmpeg 运行库，已尝试直接播放原始视频。"

    output_path = input_path.with_name(f"{input_path.stem}.browser.mp4")
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-i",
        str(input_path),
        "-vcodec",
        "libx264",
        "-acodec",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        short_detail = detail.strip().splitlines()[-1] if detail.strip() else "转换失败"
        return input_path, f"FFmpeg 转换未完成，已尝试直接播放原始视频：{short_detail}"

    if not output_path.exists() or output_path.stat().st_size == 0:
        return input_path, "FFmpeg 未生成可播放文件，已尝试直接播放原始视频。"

    if completed.stderr:
        return output_path, None
    return output_path, None


def guess_video_mime(path: Path) -> str:
    known_types = {
        ".mp4": "video/mp4",
        ".m4v": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
    }
    return known_types.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "video/mp4"


def video_to_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{guess_video_mime(path)};base64,{encoded}"


def format_time(seconds: float | int | None) -> str:
    if seconds is None:
        seconds = 0
    seconds = max(float(seconds), 0.0)
    minutes = int(seconds // 60)
    whole_seconds = int(seconds % 60)
    centiseconds = int(round((seconds - int(seconds)) * 100))
    if centiseconds == 100:
        whole_seconds += 1
        centiseconds = 0
    return f"{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"
