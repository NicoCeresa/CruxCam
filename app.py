"""CruxCam - Climbing Efficiency Analyzer with Pose Detection."""
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import tempfile
import time
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
            processor = VideoProcessor(PoseAnalyzer(angle_threshold=angle_threshold))
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

with tab3:
    st.header("About CruxCam")
    
    st.markdown(
        """
        ### Purpose
        CruxCam analyzes climbing videos to provide feedback on technique efficiency. 
        By tracking arm angles and body position, it identifies when you're using 
        optimal form (extended arms) versus inefficient form (compressed, bent arms).
        
        ### Technology
        - **MediaPipe Pose Detection**: Real-time pose estimation
        - **OpenCV**: Video processing and analysis
        - **Streamlit**: Interactive web interface
        
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
        - 3D pose estimation
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