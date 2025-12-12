# CruxCam - Climbing Efficiency Analyzer 🧗# CruxCam



A Streamlit-based web application that analyzes climbing videos using pose detection to measure technique efficiency and provide actionable feedback.## Next Steps

- section out code into python files

## 🌟 Features- input as link to instagram reel or mp4

    - instagram api?

- **Video Upload**: Support for multiple video formats (MP4, MOV, AVI, MKV)- checks

- **Real-time Analysis**: Uses MediaPipe for accurate pose detection    - video length

- **Efficiency Scoring**: Measures climbing efficiency based on arm positioning    - input dtype (mp4)

- **Visual Feedback**: Overlay with green (good) and red (bad) form indicators- impliment 3d pose estimation paper XD
- **Downloadable Results**: Export analyzed videos with annotations
- **Interactive UI**: Clean Streamlit interface with progress tracking

## 📁 Project Structure

```
CruxCam/
├── app.py                      # Main Streamlit application
├── core/                       # Core analysis modules
│   ├── __init__.py
│   ├── pose_analyzer.py        # Pose detection and analysis logic
│   └── video_processor.py      # Video I/O and processing
├── inputs/                     # Input videos directory
├── outputs/                    # Processed videos directory
├── scripts/                    # Utility scripts
│   └── run_test_models_OLD.py  # Legacy implementation (reference)
├── notebooks/                  # Jupyter notebooks for experimentation
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Virtual environment (recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/NicoCeresa/CruxCam.git
   cd CruxCam
   ```

2. **Activate virtual environment**
   ```bash
   source CruxCam/bin/activate  # Linux/Mac
   # or
   CruxCam\Scripts\activate      # Windows
   ```

3. **Install dependencies** (if not already installed)
   ```bash
   pip install streamlit opencv-python mediapipe numpy
   ```

### Running the Application

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

## 📖 Usage

1. **Upload Video**: 
   - Click on "Choose a video file" to upload your climbing video
   - Or check "Use sample video" to try with a pre-loaded example

2. **Adjust Settings**:
   - Use the sidebar slider to adjust the angle threshold (default: 90°)
   - Lower threshold = more strict (fewer "good" frames)
   - Higher threshold = more lenient (more "good" frames)

3. **Process**:
   - Click "🚀 Process Video" to start analysis
   - Watch the progress bar as frames are processed
   - Wait for completion (processing time varies with video length)

4. **View Results**:
   - Switch to the "Results" tab
   - View efficiency metrics and statistics
   - Watch the annotated video
   - Download the processed video

## 🔬 How It Works

### Pose Detection
- Uses **MediaPipe Pose** to detect 33 body landmarks per frame
- Focuses on shoulder, elbow, and wrist positions for both arms

### Angle Calculation
- Calculates the angle between upper arm (shoulder-elbow) and forearm (elbow-wrist)
- Applies vector mathematics to determine joint angles

### Classification
- **Good Frame**: Arm angles exceed the threshold (extended arms = efficient)
- **Bad Frame**: Both arm angles below threshold (bent arms = inefficient)

### Visual Feedback
- 🟡 Yellow: Body landmarks
- 🟢 Green connections: Good form
- 🔴 Red connections: Poor form
- Overlay shows real-time efficiency, good/bad frame counts

## 🏗️ Architecture Benefits

### Modular Design
- **Separation of Concerns**: UI (app.py) separated from logic (core/)
- **Reusability**: Core modules can be used independently
- **Testability**: Easy to unit test individual components

### Core Modules

**`pose_analyzer.py`**
- Encapsulates all pose detection logic
- Handles angle calculations
- Manages frame classification and visualization

**`video_processor.py`**
- Manages video I/O operations
- Coordinates pose analysis pipeline
- Provides progress callbacks for UI

### Advantages Over Old Structure
✅ **No subprocess calls** - Direct Python integration  
✅ **No hardcoded paths** - Flexible file handling  
✅ **Streamlit-native** - No OpenCV windows, pure web UI  
✅ **Better error handling** - Graceful failures with user feedback  
✅ **Progress tracking** - Real-time feedback during processing  
✅ **State management** - Session state for result persistence  

## 🎯 Metrics Explained

- **Climbing Efficiency**: `(good_frames / total_frames) * 100`
- **Good Frames**: Count of frames with proper arm extension
- **Bad Frames**: Count of frames with compressed/bent arms

### Interpretation
- **70%+**: Excellent technique
- **50-69%**: Room for improvement
- **<50%**: Focus on arm extension practice

## 🔮 Future Enhancements

- [ ] Instagram reel integration
- [ ] 3D pose estimation
- [ ] Video validation (length, format)
- [ ] Multiple climber tracking
- [ ] Historical progress tracking
- [ ] Custom angle thresholds per arm
- [ ] Export analysis data (JSON/CSV)
- [ ] Comparison mode (before/after)

## 🐛 Troubleshooting

**Issue**: Video won't process  
**Solution**: Ensure video codec is supported. Try converting to MP4 (H.264)

**Issue**: Slow processing  
**Solution**: Processing time is proportional to video length. Consider trimming videos

**Issue**: Poor pose detection  
**Solution**: Ensure good lighting and full body visibility in the video

## 📝 Development Notes

### Running Tests
```bash
# If you add tests in the future
pytest tests/
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints where applicable
- Document functions with docstrings

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is for educational and personal use.

## 🙏 Acknowledgments

- MediaPipe team for pose detection
- Streamlit for the web framework
- OpenCV community

## 📧 Contact

**Nicolas Ceresa**  
GitHub: [@NicoCeresa](https://github.com/NicoCeresa)

---

Built with ❤️ for climbers
