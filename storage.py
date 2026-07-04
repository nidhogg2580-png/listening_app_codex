from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROJECT_FILE = BASE_DIR / "project.json"


def default_project() -> dict[str, Any]:
    return {
        "video_name": "",
        "video_path": "",
        "source_video_path": "",
        "clips": [],
    }


def ensure_directories() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def to_project_path(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(BASE_DIR).as_posix()
    except ValueError:
        return resolved.as_posix()


def from_project_path(path: str | Path | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return BASE_DIR / candidate


def normalize_project(raw_project: dict[str, Any] | None) -> dict[str, Any]:
    project = default_project()
    if isinstance(raw_project, dict):
        project.update({key: raw_project.get(key, project[key]) for key in project})

    normalized_clips: list[dict[str, Any]] = []
    for index, raw_clip in enumerate(project.get("clips", []), start=1):
        if not isinstance(raw_clip, dict):
            continue
        try:
            start = float(raw_clip.get("start", 0))
            end = float(raw_clip.get("end", 0))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        normalized_clips.append(
            {
                "id": index,
                "start": round(start, 3),
                "end": round(end, 3),
                "subtitle_cn": str(raw_clip.get("subtitle_cn", "")),
                "subtitle_en": str(raw_clip.get("subtitle_en", "")),
            }
        )

    project["clips"] = normalized_clips
    project["video_name"] = str(project.get("video_name") or "")
    project["video_path"] = str(project.get("video_path") or "")
    project["source_video_path"] = str(project.get("source_video_path") or "")
    return project


def load_project(project_file: Path = PROJECT_FILE) -> dict[str, Any]:
    ensure_directories()
    if not project_file.exists():
        return default_project()
    try:
        with project_file.open("r", encoding="utf-8") as file:
            return normalize_project(json.load(file))
    except (json.JSONDecodeError, OSError):
        return default_project()


def save_project(project: dict[str, Any], project_file: Path = PROJECT_FILE) -> None:
    ensure_directories()
    clean_project = normalize_project(project)
    temporary_file = project_file.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(clean_project, file, ensure_ascii=False, indent=2)
    temporary_file.replace(project_file)


def new_project(video_name: str, video_path: Path, source_video_path: Path | None = None) -> dict[str, Any]:
    project = default_project()
    project["video_name"] = video_name
    project["video_path"] = to_project_path(video_path)
    project["source_video_path"] = to_project_path(source_video_path or video_path)
    return project


def get_clip(project: dict[str, Any], clip_id: int | None) -> dict[str, Any] | None:
    if clip_id is None:
        return None
    for clip in project.get("clips", []):
        if int(clip["id"]) == int(clip_id):
            return clip
    return None


def add_clip(project: dict[str, Any], start: float, end: float) -> dict[str, Any]:
    updated_project = deepcopy(project)
    clips = list(updated_project.get("clips", []))
    clips.append(
        {
            "id": len(clips) + 1,
            "start": round(float(start), 3),
            "end": round(float(end), 3),
            "subtitle_cn": "",
            "subtitle_en": "",
        }
    )
    updated_project["clips"] = clips
    return normalize_project(updated_project)


def update_clip_subtitles(
    project: dict[str, Any],
    clip_id: int,
    subtitle_en: str,
    subtitle_cn: str,
) -> dict[str, Any]:
    updated_project = deepcopy(project)
    for clip in updated_project.get("clips", []):
        if int(clip["id"]) == int(clip_id):
            clip["subtitle_en"] = subtitle_en
            clip["subtitle_cn"] = subtitle_cn
            break
    return normalize_project(updated_project)


def delete_clip(project: dict[str, Any], clip_id: int) -> dict[str, Any]:
    updated_project = deepcopy(project)
    kept_clips = [clip for clip in updated_project.get("clips", []) if int(clip["id"]) != int(clip_id)]
    for index, clip in enumerate(kept_clips, start=1):
        clip["id"] = index
    updated_project["clips"] = kept_clips
    return normalize_project(updated_project)
