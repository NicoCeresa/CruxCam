"""CruxCam - Climbing Efficiency Analyzer with Pose Detection."""
import os
from typing import Optional
import streamlit as st
from pathlib import Path
import tempfile
import time
import cv2
import numpy as np
import plotly.graph_objects as go
import mediapipe as mp
import requests
from core.pose_analyzer import AnalysisResult
from api.tasks import deserialize_result

API_BASE_URL = os.environ.get("CRUXCAM_API_URL", "http://localhost:8000")


@st.cache_data
def _get_video_frame(video_path: str, frame_num: int):
    """Seek to a specific frame in the processed video and return it as RGB."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    ok, frame = cap.read()
    cap.release()
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ok else None


@st.cache_data
def _fetch_preview_frame(preview_id: str, n: int) -> Optional[np.ndarray]:
    """Fetch a single frame from the preview endpoint and return as RGB ndarray."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/frame/{preview_id}",
            params={"n": n},
            timeout=5,
        )
        if resp.status_code == 200:
            arr = np.frombuffer(resp.content, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    except Exception:
        pass
    return None



@st.cache_data
def _axis_ranges(video_path: str, _detected_frames: list):
    """
    Compute equal-span axis ranges across all frames.
    All three axes get the same span (largest dimension wins) so
    aspectmode='cube' renders the skeleton without distortion.
    """
    all_x, all_y, all_z = [], [], []
    for (_, wlms, _, _) in _detected_frames:
        all_x.extend(wlms[:, 0])
        all_y.extend(wlms[:, 2])
        all_z.extend(-wlms[:, 1])

    cx = (min(all_x) + max(all_x)) / 2
    cy = (min(all_y) + max(all_y)) / 2
    cz = (min(all_z) + max(all_z)) / 2
    half = max(
        max(all_x) - min(all_x),
        max(all_y) - min(all_y),
        max(all_z) - min(all_z),
    ) / 2 + 0.1

    return (
        [cx - half, cx + half],
        [cy - half, cy + half],
        [cz - half, cz + half],
    )


@st.fragment
def _frame_review(detected_frames: list, video_path: str, fps: int) -> None:
    """
    Side-by-side annotated video frame + 3D skeleton viewer.
    A single Play/Pause button advances both panels in sync via st.rerun(scope="fragment").
    """
    max_idx = len(detected_frames) - 1

    if st.session_state.frame_idx > max_idx:
        st.session_state.frame_idx = 0

    ctrl_col, slider_col = st.columns([1, 11])
    with ctrl_col:
        btn_label = "Pause" if st.session_state.playing else "Play"
        if st.button(btn_label, use_container_width=True):
            st.session_state.playing = not st.session_state.playing

    def _on_scrub():
        st.session_state.frame_idx = st.session_state.frame_slider
        st.session_state.playing = False

    st.session_state["frame_slider"] = st.session_state.frame_idx
    with slider_col:
        st.slider(
            "Frame",
            min_value=0,
            max_value=max_idx,
            key="frame_slider",
            help="Scrub through detected pose frames",
            on_change=_on_scrub,
        )

    frame_num, world_lms, is_good, com = detected_frames[st.session_state.frame_idx]

    vid_col, pose_col = st.columns(2)

    with vid_col:
        st.caption("Annotated frame")
        frame_img = _get_video_frame(video_path, frame_num)
        if frame_img is not None:
            st.image(frame_img, use_container_width=True)
        else:
            st.warning("Could not read frame.")

    with pose_col:
        st.caption("3D skeleton")

        xs, ys, zs = world_lms[:, 0], world_lms[:, 2], -world_lms[:, 1]
        bone_color = '#4ade80' if is_good else '#f87171'
        lm_names = [lm.name for lm in mp.solutions.pose.PoseLandmark]

        bx, by, bz = [], [], []
        for s, e in mp.solutions.pose.POSE_CONNECTIONS:
            bx += [xs[s], xs[e], None]
            by += [ys[s], ys[e], None]
            bz += [zs[s], zs[e], None]

        x_range, y_range, z_range = _axis_ranges(video_path, detected_frames)

        fig = go.Figure(data=[
            go.Scatter3d(x=bx, y=by, z=bz, mode='lines',
                         line=dict(color=bone_color, width=3), name='Skeleton'),
            go.Scatter3d(x=xs, y=ys, z=zs, mode='markers',
                         marker=dict(size=3, color='#e5e7eb'), name='Joints',
                         hovertext=lm_names, hoverinfo='text'),
            go.Scatter3d(
                x=[com[0]] if com else [], y=[com[2]] if com else [], z=[-com[1]] if com else [],
                mode='markers', marker=dict(size=7, color='#60a5fa', symbol='diamond'),
                name='CoM',
            ),
        ])
        fig.update_layout(
            scene=dict(
                xaxis_title='x (m)',
                yaxis_title='depth (m)',
                zaxis_title='y (m)',
                bgcolor='#0e0e0e',
                aspectmode='cube',
                xaxis=dict(color='#6b7280', gridcolor='#1f1f1f', showbackground=False, range=x_range),
                yaxis=dict(color='#6b7280', gridcolor='#1f1f1f', showbackground=False, range=y_range),
                zaxis=dict(color='#6b7280', gridcolor='#1f1f1f', showbackground=False, range=z_range),
            ),
            paper_bgcolor='#0e0e0e',
            font=dict(color='#9ca3af', size=11),
            height=500,
            margin=dict(l=0, r=0, b=0, t=0),
            legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#6b7280', size=10)),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Metadata + download
    meta_cols = st.columns(4)
    meta_cols[0].metric("Frame", frame_num)
    meta_cols[1].metric("Classification", "Good" if is_good else "Bad")
    if com:
        meta_cols[2].metric("CoM depth", f"{com[2]:.3f} m")
    with open(video_path, 'rb') as vf:
        meta_cols[3].download_button(
            label="Download video",
            data=vf.read(),
            file_name=f"cruxcam_{time.strftime('%Y%m%d_%H%M%S')}.mp4",
            mime="video/mp4",
            use_container_width=True,
        )

    # Advance both panels in sync — only reruns this fragment
    if st.session_state.playing:
        if st.session_state.frame_idx < max_idx:
            st.session_state.frame_idx += 1
        else:
            st.session_state.playing = False
        time.sleep(1 / max(fps, 1))
        st.rerun(scope="fragment")


st.set_page_config(
    page_title="CruxCam",
    page_icon=None,
    layout="wide"
)

# Flatten Streamlit's default gradients and tighten chrome
st.markdown("""
<style>
/* Remove gradient from all buttons */
.stButton > button,
.stDownloadButton > button {
    background-image: none !important;
    border-radius: 4px !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em !important;
}
/* Remove gradient from progress bar fill */
[data-testid="stProgress"] > div > div > div > div {
    background-image: none !important;
}
/* Tighter, cleaner headings */
h1 { font-weight: 700; letter-spacing: -0.5px; margin-bottom: 0 !important; }
h2 { font-weight: 600; letter-spacing: -0.3px; }
h3 { font-weight: 600; }
/* Subtler dividers */
hr { border-color: rgba(128,128,128,0.2) !important; margin: 1.5rem 0 !important; }
/* Clean metric cards */
[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,0.15);
    border-radius: 6px;
    padding: 0.75rem 1rem;
}
/* Sidebar */
[data-testid="stSidebar"] > div:first-child {
    padding-top: 2rem;
}
</style>
""", unsafe_allow_html=True)

# Session state
if 'processed_video_path' not in st.session_state:
    st.session_state.processed_video_path = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'frame_idx' not in st.session_state:
    st.session_state.frame_idx = 0
if 'playing' not in st.session_state:
    st.session_state.playing = False
if 'video_fps' not in st.session_state:
    st.session_state.video_fps = 30
if 'preview_id' not in st.session_state:
    st.session_state.preview_id = None
if 'trim_start' not in st.session_state:
    st.session_state.trim_start = 0
if 'trim_end' not in st.session_state:
    st.session_state.trim_end = 0

# Header
st.title("CruxCam")
st.caption("Climbing efficiency analysis via pose detection.")

# Tabs
tab1, tab2 = st.tabs(["Analyze", "Compare"])

with tab1:

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Video file",
            type=['mp4', 'mov', 'avi', 'mkv'],
            help="Upload a video of your climbing session",
            label_visibility="collapsed"
        )

    with col2:
        use_sample = st.checkbox("Use sample video")
        if use_sample:
            sample_path = Path("inputs/tomoa_outside.mp4")
            if not sample_path.exists():
                st.warning("Sample video not found in inputs/")
                use_sample = False

    if uploaded_file is not None or use_sample:
        if uploaded_file is not None:
            video_bytes_for_upload = uploaded_file.read()
            video_name = uploaded_file.name
        else:
            with open(sample_path, "rb") as f:
                video_bytes_for_upload = f.read()
            video_name = sample_path.name

        # Fetch video metadata via the API
        try:
            info_resp = requests.post(
                f"{API_BASE_URL}/info",
                files={"video": (video_name, video_bytes_for_upload, "video/mp4")},
                timeout=10,
            )
            info_resp.raise_for_status()
            video_info = info_resp.json()
            st.session_state.video_fps = video_info['fps']
            st.session_state.preview_id = video_info['preview_id']
            st.session_state.trim_start = 0
            st.session_state.trim_end = video_info['total_frames'] - 1

            st.success(f"Loaded **{video_name}**")
            info_cols = st.columns(4)
            info_cols[0].metric("Duration", f"{video_info['duration']:.1f}s")
            info_cols[1].metric("Resolution", f"{video_info['width']}x{video_info['height']}")
            info_cols[2].metric("FPS", video_info['fps'])
            info_cols[3].metric("Frames", video_info['total_frames'])

        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the API server. Make sure it is running (`uvicorn api.main:app`).")
            st.stop()
        except Exception as e:
            st.error(f"Error loading video: {e}")
            st.stop()

        st.markdown("---")
        _, angle_col = st.columns([3, 1])
        with angle_col:
            angle_threshold = st.slider(
                "Angle threshold",
                min_value=30,
                max_value=120,
                value=90,
                step=5,
                help="Minimum arm angle to be considered a good frame",
            )

        st.markdown("**Trim**")
        total = video_info['total_frames']

        img_col1, slider_col, img_col2 = st.columns([1, 8, 1])

        with slider_col:
            new_start, new_end = st.slider(
                "Trim range",
                min_value=0,
                max_value=total - 1,
                value=(st.session_state.trim_start, st.session_state.trim_end),
                key="trim_range_slider",
                label_visibility="collapsed",
            )
            st.session_state.trim_start = new_start
            st.session_state.trim_end = new_end

        if st.session_state.preview_id:
            with img_col1:
                frame = _fetch_preview_frame(st.session_state.preview_id, new_start)
                if frame is not None:
                    st.image(frame, use_container_width=True)
                    st.caption(f"{new_start}")
            with img_col2:
                frame = _fetch_preview_frame(st.session_state.preview_id, new_end)
                if frame is not None:
                    st.image(frame, use_container_width=True)
                    st.caption(f"{new_end}")

        trimmed_frames = st.session_state.trim_end - st.session_state.trim_start
        trimmed_duration = trimmed_frames / max(video_info['fps'], 1)
        st.caption(f"{trimmed_frames} frames · {trimmed_duration:.1f}s selected")

        st.markdown("---")
        if st.button("Process video", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            progress_text = st.empty()

            try:
                # Upload and enqueue
                upload_resp = requests.post(
                    f"{API_BASE_URL}/upload",
                    files={"video": (video_name, video_bytes_for_upload, "video/mp4")},
                    params={
                        "angle_threshold": angle_threshold,
                        "use_3d": True,
                        "start_frame": st.session_state.trim_start,
                        "end_frame": st.session_state.trim_end,
                        "preview_id": st.session_state.preview_id,
                    },
                    timeout=30,
                )
                upload_resp.raise_for_status()
                job_id = upload_resp.json()["job_id"]

                # Poll until done
                while True:
                    status_resp = requests.get(
                        f"{API_BASE_URL}/status/{job_id}", timeout=5
                    )
                    status_resp.raise_for_status()
                    status = status_resp.json()

                    if status["status"] == "complete":
                        progress_bar.progress(1.0, text="Done")
                        break
                    if status["status"] == "failed":
                        raise RuntimeError(status.get("error", "Processing failed"))

                    if status["status"] in ("pending", "processing") and status.get("progress", 0.0) == 0.0:
                        progress_bar.progress(0.0, text="Waiting for worker...")
                    else:
                        progress = status.get("progress", 0.0)
                        trimmed_total = max(1, st.session_state.trim_end - st.session_state.trim_start)
                        current = int(progress * trimmed_total)
                        progress_bar.progress(progress, text=f"Frame {current} / {trimmed_total}")
                    time.sleep(0.1)

                # Fetch and deserialize result
                result_resp = requests.get(
                    f"{API_BASE_URL}/result/{job_id}", timeout=10
                )
                result_resp.raise_for_status()
                result = deserialize_result(result_resp.json())

                st.session_state.processed_video_path = result.processed_video_path
                st.session_state.analysis_result = result
                st.session_state.frame_idx = 0
                st.session_state.playing = False

                progress_bar.empty()
                progress_text.empty()

                st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.analysis_result is not None:
        result = st.session_state.analysis_result

        st.markdown("---")

        # Metrics
        metric_cols = st.columns(3)
        metric_cols[0].metric(
            "Climbing efficiency",
            f"{result.efficiency:.1f}%",
            help="Percentage of frames with good arm positions"
        )
        metric_cols[1].metric(
            "Good frames",
            result.good_frames,
            help="Frames with proper arm extension"
        )
        metric_cols[2].metric(
            "Bad frames",
            result.bad_frames,
            delta=f"-{result.bad_frames}",
            delta_color="inverse",
            help="Frames with compressed arm positions"
        )

        # Insights
        st.markdown("---")
        st.markdown("**Insights**")
        if result.efficiency >= 70:
            st.markdown(
                "Good efficiency. You kept your arms extended for most of the climb, "
                "letting your skeleton bear the load rather than your muscles."
            )
        elif result.efficiency >= 50:
            st.markdown(
                "Room to improve. Pulling into the wall with bent arms burns through your forearms quickly. "
                "Try to straighten up between moves and drive upward with your legs."
            )
        else:
            st.markdown(
                "Most of this climb was spent in a compressed position. "
                "Focus on straight-arm hangs, pushing with your feet, "
                "and only bending when actively moving to the next hold."
            )

        # Frame review
        st.markdown("---")
        st.markdown("**Frame review**")

        video_exists = Path(result.processed_video_path).exists()
        detected_frames = []
        if result.pose_data_3d:
            detected_frames = [e for e in result.pose_data_3d if e[1] is not None]

        if video_exists and detected_frames:
            _frame_review(detected_frames, result.processed_video_path, st.session_state.video_fps)
        elif video_exists:
            with open(result.processed_video_path, 'rb') as vf:
                video_bytes = vf.read()
            st.video(video_bytes)
            st.download_button(
                label="Download video",
                data=video_bytes,
                file_name=f"cruxcam_{time.strftime('%Y%m%d_%H%M%S')}.mp4",
                mime="video/mp4"
            )
        else:
            st.warning("Processed video file not found.")

with tab2:
    st.markdown("Video comparison coming soon.")

st.markdown("---")
st.caption("CruxCam — climbing efficiency analysis")
