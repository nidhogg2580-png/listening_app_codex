from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from storage import (
    BASE_DIR,
    STATIC_DIR,
    STATIC_UPLOAD_DIR,
    UPLOAD_DIR,
    add_clip,
    delete_clip,
    from_project_path,
    get_clip,
    load_project,
    new_project,
    save_project,
    update_clip_subtitles,
)
from utils import (
    SUPPORTED_VIDEO_TYPES,
    convert_to_browser_mp4,
    copy_to_static_upload,
    format_time,
    save_uploaded_file,
    static_file_url,
)


COMPONENT_DIR = BASE_DIR / "components" / "video_player"
video_player_component = components.declare_component("video_player", path=str(COMPONENT_DIR))


st.set_page_config(
    page_title="Repeated Listening Platform",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1180px;
            padding-top: 1.35rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        .app-title {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 1rem;
            border-bottom: 1px solid #e5e7eb;
            padding-bottom: 0.75rem;
            margin-bottom: 1rem;
        }
        .app-title h1 {
            font-size: clamp(1.45rem, 2vw, 2rem);
            margin: 0;
        }
        .project-pill {
            color: #334155;
            background: #eef2ff;
            border: 1px solid #c7d2fe;
            border-radius: 999px;
            padding: 0.28rem 0.7rem;
            font-size: 0.85rem;
            white-space: nowrap;
        }
        .panel-title {
            color: #111827;
            font-size: 0.9rem;
            font-weight: 700;
            margin: 0.25rem 0 0.65rem;
        }
        .clip-row {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.55rem 0.65rem;
            margin: 0.45rem 0;
            background: #ffffff;
        }
        .clip-row-active {
            border-color: #2563eb;
            background: #eff6ff;
        }
        .clip-meta {
            color: #64748b;
            font-size: 0.78rem;
            margin-top: -0.2rem;
            margin-bottom: 0.25rem;
        }
        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius: 8px;
        }
        div[data-testid="stTextArea"] textarea {
            border-radius: 8px;
        }
        @media (max-width: 820px) {
            .app-title {
                align-items: flex-start;
                flex-direction: column;
            }
            .project-pill {
                white-space: normal;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    if "project" not in st.session_state:
        st.session_state.project = load_project()
    if "active_clip_id" not in st.session_state:
        st.session_state.active_clip_id = None
    if "pending_start" not in st.session_state:
        st.session_state.pending_start = None
    if "loop_enabled" not in st.session_state:
        st.session_state.loop_enabled = False
    if "last_player_event_id" not in st.session_state:
        st.session_state.last_player_event_id = None
    if "status_message" not in st.session_state:
        st.session_state.status_message = None
    if "study_mode" not in st.session_state:
        st.session_state.study_mode = "📺 完整视频模式"
    if "pending_study_mode" not in st.session_state:
        st.session_state.pending_study_mode = None
    if "last_upload_signature" not in st.session_state:
        st.session_state.last_upload_signature = None


def set_status(kind: str, text: str) -> None:
    st.session_state.status_message = {"kind": kind, "text": text}


def set_study_mode(mode: str) -> None:
    st.session_state.study_mode = mode
    st.session_state.pending_study_mode = mode


def show_status() -> None:
    message = st.session_state.get("status_message")
    if not message:
        return
    kind = message.get("kind")
    text = message.get("text", "")
    if kind == "success":
        st.success(text)
    elif kind == "warning":
        st.warning(text)
    elif kind == "error":
        st.error(text)
    else:
        st.info(text)


def current_video_path(project: dict[str, Any]) -> Path | None:
    path = from_project_path(project.get("video_path"))
    if path and path.exists():
        return path
    return None


def build_video_source(path: Path) -> str:
    try:
        path.resolve().relative_to(STATIC_DIR.resolve())
    except ValueError:
        path = copy_to_static_upload(path, STATIC_UPLOAD_DIR)
    return static_file_url(path, STATIC_DIR)


def handle_upload() -> None:
    uploaded_file = st.file_uploader(
        "上传视频",
        type=list(SUPPORTED_VIDEO_TYPES),
        accept_multiple_files=False,
    )
    if not uploaded_file:
        return

    signature = f"{uploaded_file.name}:{uploaded_file.size}"
    if signature == st.session_state.last_upload_signature:
        return

    with st.spinner("正在保存视频"):
        saved_path = save_uploaded_file(uploaded_file, UPLOAD_DIR)
        playable_path, warning = convert_to_browser_mp4(saved_path)
        static_playable_path = copy_to_static_upload(playable_path, STATIC_UPLOAD_DIR)
        project = new_project(uploaded_file.name, static_playable_path, saved_path)
        save_project(project)

    st.session_state.project = project
    st.session_state.active_clip_id = None
    st.session_state.pending_start = None
    st.session_state.loop_enabled = False
    set_study_mode("📺 完整视频模式")
    st.session_state.last_upload_signature = signature
    if warning:
        set_status("warning", warning)
    else:
        set_status("success", "视频已导入。")
    st.rerun()


def select_clip(clip_id: int) -> None:
    st.session_state.active_clip_id = clip_id
    st.session_state.loop_enabled = True
    set_study_mode("✂️ 片段学习模式")


def select_adjacent_clip(direction: int) -> None:
    clips = st.session_state.project.get("clips", [])
    if not clips:
        return
    ids = [int(clip["id"]) for clip in clips]
    active_id = st.session_state.active_clip_id if st.session_state.active_clip_id in ids else ids[0]
    active_index = ids.index(active_id)
    next_index = (active_index + direction) % len(ids)
    select_clip(ids[next_index])


def ensure_active_clip_is_valid() -> None:
    clips = st.session_state.project.get("clips", [])
    ids = [int(clip["id"]) for clip in clips]
    if st.session_state.active_clip_id in ids:
        return
    st.session_state.active_clip_id = ids[0] if ids else None
    if not ids:
        st.session_state.loop_enabled = False


def render_clip_list() -> None:
    project = st.session_state.project
    clips = project.get("clips", [])
    st.markdown('<div class="panel-title">Clip 列表</div>', unsafe_allow_html=True)

    if not clips:
        st.info("暂无 Clip")
        return

    for clip in clips:
        is_active = int(clip["id"]) == st.session_state.active_clip_id
        row_class = "clip-row clip-row-active" if is_active else "clip-row"
        st.markdown(f'<div class="{row_class}">', unsafe_allow_html=True)
        st.caption(f'{format_time(clip["start"])} → {format_time(clip["end"])}')
        button_type = "primary" if is_active else "secondary"
        if st.button(f'Clip {clip["id"]}', key=f"select_clip_{clip['id']}", type=button_type, use_container_width=True):
            select_clip(int(clip["id"]))
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_left_panel() -> None:
    with st.container(border=True):
        st.markdown('<div class="panel-title">视频</div>', unsafe_allow_html=True)
        handle_upload()

        video_name = st.session_state.project.get("video_name")
        if video_name:
            st.caption(video_name)

        save_col, clear_col = st.columns(2)
        with save_col:
            if st.button("保存项目", use_container_width=True):
                save_project(st.session_state.project)
                set_status("success", "project.json 已保存。")
                st.rerun()
        with clear_col:
            if st.button("停止循环", use_container_width=True):
                st.session_state.loop_enabled = False
                set_status("success", "循环已停止。")
                st.rerun()

    with st.container(border=True):
        render_clip_list()


def handle_player_event(event: Any) -> None:
    if not isinstance(event, dict):
        return

    event_id = event.get("event_id")
    if not event_id or event_id == st.session_state.last_player_event_id:
        return
    st.session_state.last_player_event_id = event_id

    event_name = event.get("event")
    try:
        current_time = round(float(event.get("current_time", 0)), 3)
    except (TypeError, ValueError):
        current_time = 0.0

    if event_name == "mark_start":
        st.session_state.pending_start = current_time
        set_status("success", f"已标记起点：{format_time(current_time)}")
        st.rerun()

    if event_name == "mark_end":
        start_time = st.session_state.pending_start
        if start_time is None:
            set_status("error", "请先标记起点。")
            st.rerun()
        if current_time <= float(start_time):
            set_status("error", "终点必须晚于起点。")
            st.rerun()

        project = add_clip(st.session_state.project, float(start_time), current_time)
        save_project(project)
        new_clip_id = len(project["clips"])
        st.session_state.project = project
        st.session_state.active_clip_id = new_clip_id
        st.session_state.loop_enabled = True
        st.session_state.pending_start = None
        set_study_mode("✂️ 片段学习模式")
        set_status("success", f"Clip {new_clip_id} 已创建。")
        st.rerun()


def render_player(video_source: str, mode: str) -> None:
    project = st.session_state.project
    active_clip = get_clip(project, st.session_state.active_clip_id)
    clip_mode = mode.startswith("✂️")
    component_active_clip = active_clip if clip_mode else None
    loop_enabled = bool(clip_mode and active_clip and st.session_state.loop_enabled)

    player_event = video_player_component(
        videoUrl=video_source,
        activeClip=component_active_clip,
        loop=loop_enabled,
        pendingStart=st.session_state.pending_start,
        mode="clip" if clip_mode else "full",
        key="main_video_player",
        default=None,
    )
    handle_player_event(player_event)


def render_clip_controls() -> None:
    clips = st.session_state.project.get("clips", [])
    active_clip = get_clip(st.session_state.project, st.session_state.active_clip_id)
    previous_col, next_col, delete_col = st.columns(3)

    with previous_col:
        if st.button("上一 Clip", use_container_width=True, disabled=not clips):
            select_adjacent_clip(-1)
            st.rerun()
    with next_col:
        if st.button("下一 Clip", use_container_width=True, disabled=not clips):
            select_adjacent_clip(1)
            st.rerun()
    with delete_col:
        if st.button("删除 Clip", use_container_width=True, disabled=active_clip is None):
            deleted_id = st.session_state.active_clip_id
            project = delete_clip(st.session_state.project, int(deleted_id))
            save_project(project)
            st.session_state.project = project
            ensure_active_clip_is_valid()
            st.session_state.loop_enabled = bool(st.session_state.active_clip_id)
            set_status("success", "Clip 已删除并重新编号。")
            st.rerun()


def render_subtitle_editor() -> None:
    active_clip = get_clip(st.session_state.project, st.session_state.active_clip_id)
    if not active_clip:
        st.info("选择一个 Clip 后可编辑字幕。")
        return

    st.markdown(f"### Clip {active_clip['id']} 字幕")
    with st.form(key=f"subtitle_form_{active_clip['id']}"):
        subtitle_en = st.text_area(
            "英文字幕",
            value=active_clip.get("subtitle_en", ""),
            height=90,
        )
        subtitle_cn = st.text_area(
            "中文字幕",
            value=active_clip.get("subtitle_cn", ""),
            height=90,
        )
        submitted = st.form_submit_button("保存字幕", use_container_width=True)

    if submitted:
        project = update_clip_subtitles(
            st.session_state.project,
            int(active_clip["id"]),
            subtitle_en,
            subtitle_cn,
        )
        save_project(project)
        st.session_state.project = project
        set_status("success", "字幕已保存。")
        st.rerun()


def render_main_panel() -> None:
    ensure_active_clip_is_valid()
    project = st.session_state.project
    video_path = current_video_path(project)

    pending_mode = st.session_state.pending_study_mode
    if pending_mode:
        st.session_state.study_mode = pending_mode
        st.session_state.study_mode_widget = pending_mode
        st.session_state.pending_study_mode = None
    elif "study_mode_widget" not in st.session_state:
        st.session_state.study_mode_widget = st.session_state.study_mode
    else:
        st.session_state.study_mode = st.session_state.study_mode_widget

    mode = st.radio(
        "学习模式",
        ["📺 完整视频模式", "✂️ 片段学习模式"],
        horizontal=True,
        label_visibility="collapsed",
        key="study_mode_widget",
    )
    st.session_state.study_mode = mode
    clip_mode = mode.startswith("✂️")

    show_status()

    if not project.get("video_path"):
        st.info("请先上传视频。")
        return

    if not video_path:
        st.error("project.json 中的视频文件不存在，请重新上传。")
        return

    video_source = build_video_source(video_path)

    render_player(video_source, mode)

    if st.session_state.pending_start is not None:
        st.caption(f"当前起点：{format_time(st.session_state.pending_start)}")

    if clip_mode:
        render_clip_controls()
        render_subtitle_editor()
    else:
        st.caption("完整视频模式")


def render_header() -> None:
    project = st.session_state.project
    label = project.get("video_name") or "未导入视频"
    st.markdown(
        f"""
        <div class="app-title">
          <h1>Repeated Listening Platform</h1>
          <span class="project-pill">{label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_styles()
    init_state()
    render_header()
    left_col, right_col = st.columns([0.3, 0.7], gap="large")
    with left_col:
        render_left_panel()
    with right_col:
        render_main_panel()


if __name__ == "__main__":
    main()
