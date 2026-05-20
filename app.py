"""CruxCam - Climbing Efficiency Analyzer with Pose Detection."""
import os
import streamlit as st
import streamlit.components.v1 as components
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


@st.fragment
def _frame_review(detected_frames: list, video_path: str) -> None:
    """
    Renders the side-by-side video frame + 3D skeleton viewer.
    Decorated as a fragment so the play loop only reruns this section,
    not the full page (header, sidebar, other tabs stay frozen).
    """
    mp_pose = mp.solutions.pose
    max_idx = len(detected_frames) - 1

    if st.session_state.frame_idx > max_idx:
        st.session_state.frame_idx = 0

    # Single toggle button + slider in one row
    ctrl_col, slider_col = st.columns([1, 11])
    with ctrl_col:
        btn_label = "Pause" if st.session_state.playing else "Play"
        if st.button(btn_label, use_container_width=True):
            st.session_state.playing = not st.session_state.playing

    def _on_scrub():
        st.session_state.frame_idx = st.session_state.frame_slider
        st.session_state.playing = False

    # Sync slider position to frame_idx before rendering (must happen before instantiation)
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

        xs = world_lms[:, 0]
        ys = world_lms[:, 2]
        zs = -world_lms[:, 1]

        bone_color = '#4ade80' if is_good else '#f87171'
        fig = go.Figure()

        bone_x, bone_y, bone_z = [], [], []
        for start, end in mp_pose.POSE_CONNECTIONS:
            bone_x += [xs[start], xs[end], None]
            bone_y += [ys[start], ys[end], None]
            bone_z += [zs[start], zs[end], None]
        fig.add_trace(go.Scatter3d(
            x=bone_x, y=bone_y, z=bone_z,
            mode='lines',
            line=dict(color=bone_color, width=3),
            name='Skeleton',
        ))

        lm_names = [lm.name for lm in mp_pose.PoseLandmark]
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode='markers',
            marker=dict(size=3, color='#e5e7eb'),
            name='Joints',
            hovertext=lm_names,
            hoverinfo='text',
        ))

        com_xs, com_ys, com_zs = [], [], []
        for (_, _, _, c) in detected_frames:
            if c:
                com_xs.append(c[0])
                com_ys.append(c[2])
                com_zs.append(-c[1])
        if com_xs:
            fig.add_trace(go.Scatter3d(
                x=com_xs, y=com_ys, z=com_zs,
                mode='lines',
                line=dict(color='rgba(96,165,250,0.4)', width=2),
                name='CoM path',
            ))

        if com:
            fig.add_trace(go.Scatter3d(
                x=[com[0]], y=[com[2]], z=[-com[1]],
                mode='markers',
                marker=dict(size=7, color='#60a5fa', symbol='diamond'),
                name='CoM',
            ))

        fig.update_layout(
            scene=dict(
                xaxis_title='x (m)',
                yaxis_title='depth (m)',
                zaxis_title='y (m)',
                bgcolor='#0e0e0e',
                xaxis=dict(color='#6b7280', gridcolor='#1f1f1f', showbackground=False),
                yaxis=dict(color='#6b7280', gridcolor='#1f1f1f', showbackground=False),
                zaxis=dict(color='#6b7280', gridcolor='#1f1f1f', showbackground=False),
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

    # Auto-advance — only reruns this fragment, not the full page
    if st.session_state.playing:
        if st.session_state.frame_idx < max_idx:
            st.session_state.frame_idx += 1
        else:
            st.session_state.playing = False
        time.sleep(0.06)  # ~16 fps
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

# Header
st.title("CruxCam")
st.caption("Climbing efficiency analysis via pose detection.")

# Sidebar
with st.sidebar:
    st.markdown("**Settings**")
    angle_threshold = st.slider(
        "Angle threshold (degrees)",
        min_value=30,
        max_value=120,
        value=90,
        step=5,
        help="Minimum arm angle to be considered a good frame"
    )

    use_3d = st.toggle(
        "3D pose mode",
        value=True,
        help="Use 3D world landmarks for angle and CoM calculations. More accurate for arms reaching toward or away from the camera."
    )

    st.markdown("---")
    st.markdown(
        """
        **Key**
        - Green skeleton — good arm position
        - Red skeleton — compressed arm position
        - Blue dot — center of mass
        """
    )

# Tabs
tab1, tab2, tab3 = st.tabs(["Upload", "Results", "About"])

with tab1:
    st.subheader("Upload video")

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
        if st.button("Process video", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            progress_text = st.empty()

            try:
                # Upload and enqueue
                upload_resp = requests.post(
                    f"{API_BASE_URL}/upload",
                    files={"video": (video_name, video_bytes_for_upload, "video/mp4")},
                    params={"angle_threshold": angle_threshold, "use_3d": use_3d},
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
                        progress_bar.progress(1.0)
                        break
                    if status["status"] == "failed":
                        raise RuntimeError(status.get("error", "Processing failed"))

                    progress = status.get("progress", 0.0)
                    current = int(progress * video_info["total_frames"])
                    total = video_info["total_frames"]
                    progress_bar.progress(progress)
                    progress_text.text(f"Frame {current} / {total}")
                    time.sleep(0.5)

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

                st.success("Done. See the Results tab.")
                components.html("""
                    <script>
                        const tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
                        for (const tab of tabs) {
                            if (tab.innerText.includes("Results")) {
                                tab.click();
                                break;
                            }
                        }
                    </script>
                """, height=0)

            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.subheader("Results")

    if st.session_state.analysis_result is None:
        st.markdown("Upload and process a video to see results here.")
    else:
        result = st.session_state.analysis_result

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

        # Side-by-side frame review
        st.markdown("---")
        st.markdown("**Frame review**")

        video_exists = Path(result.processed_video_path).exists()
        detected_frames = []
        if result.pose_data_3d:
            detected_frames = [e for e in result.pose_data_3d if e[1] is not None]

        if video_exists and detected_frames:
            _frame_review(detected_frames, result.processed_video_path)

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

with tab3:
    st.subheader("About")

    st.markdown(
        """
        CruxCam analyzes climbing videos to provide feedback on technique efficiency.
        By tracking arm angles and body position, it identifies when you are using
        optimal form (extended arms) versus inefficient form (compressed, bent arms).

        **Technology**
        - MediaPipe Pose — 2D/3D landmark detection
        - OpenCV — video processing
        - Streamlit — interface
        - Plotly — 3D skeleton viewer

        **Metrics**
        - Good frames — arm angle exceeds the threshold
        - Bad frames — both arms compressed below the threshold
        - Efficiency — good frames as a percentage of total analyzed frames

        **Visual indicators on the processed video**
        - Yellow dots — detected body landmarks
        - Green connections — good form
        - Red connections — poor form
        - Blue dot — center of mass (labeled with depth when in 3D mode)

        **Planned**
        - Instagram reel integration
        - Multiple climber tracking
        - Historical progress tracking
        """
    )

st.markdown("---")
st.caption("CruxCam — climbing efficiency analysis")
