"""CruxCam - Climbing Efficiency Analyzer with Pose Detection."""
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import tempfile
import time
import numpy as np
import plotly.graph_objects as go
import mediapipe as mp
from core.pose_analyzer import PoseAnalyzer
from core.video_processor import VideoProcessor

# Page configuration
st.set_page_config(
    page_title="CruxCam - Climbing Efficiency Analyzer",
    page_icon="🧗",
    layout="wide"
)

# Initialize session state
if 'processed_video_path' not in st.session_state:
    st.session_state.processed_video_path = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None

# Header
st.title("🧗 CruxCam")
st.markdown(
    """
    Upload a climbing video to analyze your technique and efficiency.
    CruxCam uses pose detection to identify good and bad arm positions during your climb.
    """
)

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    angle_threshold = st.slider(
        "Angle Threshold (degrees)",
        min_value=30,
        max_value=120,
        value=90,
        step=5,
        help="Minimum arm angle to be considered a 'good' frame"
    )

    use_3d = st.toggle(
        "3D Pose Mode",
        value=True,
        help="Use 3D world landmarks for angle and CoM calculations. More accurate for arms reaching toward or away from the camera."
    )

    st.markdown("---")
    st.markdown(
        """
        ### How it works
        - 🟢 **Green**: Good arm positions (extended)
        - 🔴 **Red**: Bad arm positions (bent/compressed)
        - 📊 Efficiency score based on good vs bad frames
        """
    )

# Main content area
tab1, tab2, tab3 = st.tabs(["📤 Upload & Process", "📊 Results", "ℹ️ About"])

with tab1:
    st.header("Upload Video")
    
    # Create two columns for input options
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'mov', 'avi', 'mkv'],
            help="Upload a video of your climbing session"
        )
    
    with col2:
        st.markdown("**Or use sample video**")
        use_sample = st.checkbox("Use sample video")
        if use_sample:
            sample_path = Path("inputs/tomoa_outside.mp4")
            if not sample_path.exists():
                st.warning("Sample video not found in inputs/")
                use_sample = False
    
    # Process video
    if uploaded_file is not None or use_sample:
        # Save uploaded file to temporary location
        if uploaded_file is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                tmp_file.write(uploaded_file.read())
                input_video_path = tmp_file.name
            video_name = uploaded_file.name
        else:
            input_video_path = str(sample_path)
            video_name = sample_path.name
        
        # Display video info
        try:
            processor = VideoProcessor(PoseAnalyzer(angle_threshold=angle_threshold, use_3d=use_3d))
            video_info = processor.get_video_info(input_video_path)
            
            st.success(f"✅ Video loaded: **{video_name}**")
            
            info_cols = st.columns(4)
            with info_cols[0]:
                st.metric("Duration", f"{video_info['duration']:.1f}s")
            with info_cols[1]:
                st.metric("Resolution", f"{video_info['width']}x{video_info['height']}")
            with info_cols[2]:
                st.metric("FPS", video_info['fps'])
            with info_cols[3]:
                st.metric("Frames", video_info['total_frames'])
            
            # Process button
            st.markdown("---")
            process_button = st.button("🚀 Process Video", type="primary", use_container_width=True)
            
            if process_button:
                with st.spinner("🔄 Processing video... This may take a few minutes."):
                    # Create output path
                    output_dir = Path("outputs")
                    output_dir.mkdir(exist_ok=True)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    output_path = output_dir / f"analyzed_{timestamp}.mp4"
                    
                    # Progress bar
                    progress_bar = st.progress(0)
                    progress_text = st.empty()
                    
                    def update_progress(current, total):
                        progress = current / total
                        progress_bar.progress(progress)
                        progress_text.text(f"Processing frame {current}/{total} ({progress*100:.1f}%)")
                    
                    # Process video
                    try:
                        result = processor.process_video(
                            input_video_path,
                            str(output_path),
                            progress_callback=update_progress
                        )
                        
                        # Store results in session state
                        st.session_state.processed_video_path = str(output_path)
                        st.session_state.analysis_result = result
                        
                        progress_bar.empty()
                        progress_text.empty()
                        
                        st.success("✅ Processing complete!")
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
                        st.error(f"❌ Error processing video: {str(e)}")
                        
        except Exception as e:
            st.error(f"❌ Error loading video: {str(e)}")

with tab2:
    st.header("Analysis Results")
    
    if st.session_state.analysis_result is None:
        st.info("👈 Upload and process a video to see results here.")
    else:
        result = st.session_state.analysis_result
        
        # Display metrics
        st.subheader("📊 Performance Metrics")
        metric_cols = st.columns(3)
        
        with metric_cols[0]:
            st.metric(
                "Climbing Efficiency",
                f"{result.efficiency:.2f}%",
                help="Percentage of frames with good arm positions"
            )
        with metric_cols[1]:
            st.metric(
                "Good Frames",
                result.good_frames,
                help="Number of frames with proper arm extension"
            )
        with metric_cols[2]:
            st.metric(
                "Bad Frames",
                result.bad_frames,
                delta=f"-{result.bad_frames}",
                delta_color="inverse",
                help="Number of frames with compressed arm positions"
            )
        
        # Display processed video
        st.markdown("---")
        st.subheader("📹 Processed Video")
        
        if Path(result.processed_video_path).exists():
            with open(result.processed_video_path, 'rb') as video_file:
                video_bytes = video_file.read()
                st.video(video_bytes)
            
            # Download button
            st.download_button(
                label="⬇️ Download Processed Video",
                data=video_bytes,
                file_name=f"cruxcam_analysis_{time.strftime('%Y%m%d_%H%M%S')}.mp4",
                mime="video/mp4"
            )
        else:
            st.warning("Processed video file not found.")
        
        # Insights
        st.markdown("---")
        st.subheader("💡 Insights")

        if result.efficiency >= 70:
            st.success(
                "Great climbing! You kept your arms extended for most of the climb, letting your "
                "skeleton bear the load instead of your muscles. This is the foundation of efficient movement."
            )
        elif result.efficiency >= 50:
            st.warning(
                "You're spending too much time with bent arms. Pulling yourself into the wall burns "
                "through your forearms fast — try to straighten up between moves and use your legs to drive upward."
            )
        else:
            st.error(
                "Most of this climb was spent in a compressed, bunched-up position. "
                "This puts constant load on your arms and will drain your energy quickly. "
                "Focus on straight-arm hangs, pushing with your feet, and only bending when you're actively moving to the next hold."
            )

        # 3D Pose Viewer
        st.markdown("---")
        st.subheader("🎯 3D Pose Viewer")

        if result.pose_data_3d:
            detected_frames = [
                (i, entry) for i, entry in enumerate(result.pose_data_3d)
                if entry[1] is not None
            ]

            if detected_frames:
                mp_pose = mp.solutions.pose

                slider_idx = st.slider(
                    "Frame",
                    min_value=0,
                    max_value=len(detected_frames) - 1,
                    value=len(detected_frames) // 2,
                    help="Scrub through detected pose frames"
                )

                _, (frame_num, world_lms, is_good, com) = detected_frames[slider_idx]

                # Remap axes: X=horizontal, Y=depth(world Z), Z=up(-world Y)
                xs = world_lms[:, 0]
                ys = world_lms[:, 2]
                zs = -world_lms[:, 1]

                bone_color = '#7FFF00' if is_good else '#FF3232'
                fig = go.Figure()

                # Skeleton connections (single trace with None separators)
                bone_x, bone_y, bone_z = [], [], []
                for start, end in mp_pose.POSE_CONNECTIONS:
                    bone_x += [xs[start], xs[end], None]
                    bone_y += [ys[start], ys[end], None]
                    bone_z += [zs[start], zs[end], None]
                fig.add_trace(go.Scatter3d(
                    x=bone_x, y=bone_y, z=bone_z,
                    mode='lines',
                    line=dict(color=bone_color, width=4),
                    name='Skeleton',
                ))

                # Joints
                lm_names = [lm.name for lm in mp_pose.PoseLandmark]
                fig.add_trace(go.Scatter3d(
                    x=xs, y=ys, z=zs,
                    mode='markers',
                    marker=dict(size=4, color='#FFFF00'),
                    name='Joints',
                    hovertext=lm_names,
                    hoverinfo='text',
                ))

                # CoM trajectory (all frames)
                com_xs, com_ys, com_zs = [], [], []
                for _, (_, _, _, c) in detected_frames:
                    if c:
                        com_xs.append(c[0])
                        com_ys.append(c[2])
                        com_zs.append(-c[1])
                if com_xs:
                    fig.add_trace(go.Scatter3d(
                        x=com_xs, y=com_ys, z=com_zs,
                        mode='lines+markers',
                        line=dict(color='rgba(0,127,255,0.35)', width=2),
                        marker=dict(size=2, color='rgba(0,127,255,0.35)'),
                        name='CoM Path',
                    ))

                # CoM for selected frame
                if com:
                    fig.add_trace(go.Scatter3d(
                        x=[com[0]], y=[com[2]], z=[-com[1]],
                        mode='markers',
                        marker=dict(size=9, color='#007FFF', symbol='diamond'),
                        name='CoM',
                    ))

                fig.update_layout(
                    scene=dict(
                        xaxis_title='Horizontal (m)',
                        yaxis_title='Depth (m)',
                        zaxis_title='Vertical (m)',
                        bgcolor='#111111',
                        xaxis=dict(color='white'),
                        yaxis=dict(color='white'),
                        zaxis=dict(color='white'),
                    ),
                    paper_bgcolor='#111111',
                    font=dict(color='white'),
                    height=520,
                    margin=dict(l=0, r=0, b=0, t=30),
                    legend=dict(bgcolor='rgba(0,0,0,0)'),
                )
                st.plotly_chart(fig, use_container_width=True)

                # Frame metadata
                info_cols = st.columns(3)
                info_cols[0].metric("Frame #", frame_num)
                info_cols[1].metric("Classification", "Good ✅" if is_good else "Bad ❌")
                if com:
                    info_cols[2].metric("CoM Depth", f"{com[2]:.3f} m")
            else:
                st.info("No frames with detectable pose found.")
        else:
            st.info("3D pose data not available. Process a video to see the viewer.")

with tab3:
    st.header("About CruxCam")
    
    st.markdown(
        """
        ### Purpose
        CruxCam analyzes climbing videos to provide feedback on technique efficiency. 
        By tracking arm angles and body position, it identifies when you're using 
        optimal form (extended arms) versus inefficient form (compressed, bent arms).
        
        ### Technology
        - **MediaPipe Pose Detection**: 2D/3D pose estimation (world landmarks)
        - **OpenCV**: Video processing and analysis
        - **Streamlit**: Interactive web interface
        - **Plotly**: Interactive 3D pose viewer
        
        ### Metrics Explained
        - **Good Frames**: Frames where arm angles exceed the threshold (proper extension)
        - **Bad Frames**: Frames where both arms are compressed below the threshold
        - **Efficiency**: Percentage of good frames relative to total analyzed frames
        
        ### Visual Indicators
        - 🟡 Yellow dots: Detected body landmarks
        - 🟢 Green connections: Good form detected
        - 🔴 Red connections: Poor form detected
        
        ### Future Features
        - Instagram reel integration
        - Video length validation
        - Multiple climber tracking
        - Historical progress tracking
        
        ### Feedback
        Found a bug or have a feature request? Open an issue on GitHub!
        """
    )

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <p>CruxCam - Climbing Efficiency Analyzer | Built with ❤️ for climbers</p>
    </div>
    """,
    unsafe_allow_html=True
)