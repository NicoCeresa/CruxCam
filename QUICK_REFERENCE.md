# CruxCam Quick Reference

## 🚀 Quick Start

### Run the Application
```bash
cd /media/nico/Games/Projects/CruxCam
streamlit run app.py
```

### Use the Web Interface
1. Upload a video (or use sample)
2. Adjust angle threshold in sidebar
3. Click "Process Video"
4. View results in "Results" tab
5. Download processed video

## 📁 Project Structure

```
CruxCam/
├── app.py                      # Main Streamlit app - START HERE
├── core/                       # Core business logic
│   ├── pose_analyzer.py        # Pose detection & analysis
│   └── video_processor.py      # Video I/O & processing
├── inputs/                     # Put input videos here
├── outputs/                    # Processed videos saved here
├── scripts/
│   ├── example_usage.py        # CLI usage example
│   └── run_test_models_OLD.py  # Legacy code (reference)
└── docs/
    ├── ARCHITECTURE.md         # System design diagrams
    ├── MIGRATION.md            # Old → New guide
    └── RESTRUCTURING_SUMMARY.md # Complete change summary
```

## 🔧 Key Files

| File | Purpose | When to Edit |
|------|---------|--------------|
| `app.py` | Streamlit UI | Change UI, add tabs, modify layout |
| `core/pose_analyzer.py` | Pose logic | Change angle calculation, thresholds |
| `core/video_processor.py` | Video I/O | Change video formats, add features |
| `scripts/example_usage.py` | CLI example | Learn API usage |

## 💻 API Usage (Programmatic)

```python
# Import modules
from core.pose_analyzer import PoseAnalyzer
from core.video_processor import VideoProcessor

# Create analyzer with custom threshold
analyzer = PoseAnalyzer(angle_threshold=90)

# Create processor
processor = VideoProcessor(pose_analyzer=analyzer)

# Process video
result = processor.process_video(
    input_path='inputs/my_video.mp4',
    output_path='outputs/analyzed.mp4',
    progress_callback=lambda cur, tot: print(f"{cur}/{tot}")
)

# Access results
print(f"Efficiency: {result.efficiency:.2f}%")
print(f"Good frames: {result.good_frames}")
print(f"Bad frames: {result.bad_frames}")
```

## 🎯 Common Tasks

### Change Angle Threshold
**In UI:** Use sidebar slider (30-120°)

**In Code:**
```python
analyzer = PoseAnalyzer(angle_threshold=75)  # More strict
```

### Process Multiple Videos
```python
from pathlib import Path
processor = VideoProcessor()

for video in Path('inputs').glob('*.mp4'):
    result = processor.process_video(
        str(video),
        f'outputs/{video.stem}_analyzed.mp4'
    )
    print(f"{video.name}: {result.efficiency:.2f}%")
```

### Get Video Info Only
```python
processor = VideoProcessor()
info = processor.get_video_info('inputs/video.mp4')
print(info)
# {'fps': 30, 'width': 1920, 'height': 1080, 
#  'total_frames': 900, 'duration': 30.0}
```

### Extract Preview Frames
```python
processor = VideoProcessor()
for frame_num, frame in processor.extract_frames('video.mp4', max_frames=5):
    cv2.imwrite(f'frame_{frame_num}.jpg', frame)
```

## 🎨 Customizing Colors

Edit `core/pose_analyzer.py`:

```python
class PoseAnalyzer:
    # Change these color constants (BGR format)
    BLUE = (255, 127, 0)
    RED = (50, 50, 255)
    GREEN = (127, 255, 0)
    YELLOW = (0, 255, 255)
    BLACK = (0, 0, 0)
```

## 📊 Understanding Results

### Efficiency Score
```
Efficiency = (Good Frames / Total Frames) × 100
```

- **70%+** = Excellent form
- **50-69%** = Room for improvement  
- **<50%** = Focus on arm extension

### Frame Classification
- **Good Frame**: Both arms extended (angles > threshold)
- **Bad Frame**: Both arms compressed (angles ≤ threshold)

### Visual Indicators
- 🟡 **Yellow dots**: Body landmarks detected
- 🟢 **Green lines**: Good form this frame
- 🔴 **Red lines**: Poor form this frame

## 🔍 Debugging

### Check for Errors
```bash
# Run with verbose output
streamlit run app.py --logger.level=debug
```

### Test Core Modules
```python
# Test pose analyzer
from core.pose_analyzer import PoseAnalyzer
import cv2
import mediapipe as mp

analyzer = PoseAnalyzer()
img = cv2.imread('test.jpg')
pose = mp.solutions.pose.Pose()

processed_img, is_good, angles = analyzer.analyze_frame(img, pose)
print(f"Good frame: {is_good}, Angles: {angles}")
```

### Verify Video Files
```python
import cv2
cap = cv2.VideoCapture('inputs/video.mp4')
print(f"Opened: {cap.isOpened()}")
print(f"FPS: {cap.get(cv2.CAP_PROP_FPS)}")
cap.release()
```

## 📦 Dependencies

```bash
# Check installed packages
pip list | grep -E "streamlit|opencv|mediapipe|numpy"

# Install missing packages
pip install streamlit opencv-python mediapipe numpy
```

## 🐛 Common Issues

### "Module not found: core"
```bash
# Make sure you're in project root
cd /media/nico/Games/Projects/CruxCam
python -m streamlit run app.py
```

### Video won't process
- Check video format (prefer MP4 with H.264)
- Ensure video file exists
- Check `outputs/` directory is writable

### Slow processing
- Processing time ≈ video length × 2
- Reduce video resolution or length
- Close other applications

### Poor pose detection
- Ensure good lighting
- Full body should be visible
- Subject should face camera
- Avoid obstructions

## 🔄 Workflow Examples

### Basic Workflow
```
1. Place video in inputs/
2. streamlit run app.py
3. Click "Use sample video"
4. Click "Process Video"
5. Check Results tab
6. Download processed video
```

### Batch Analysis Workflow
```python
from pathlib import Path
from core.pose_analyzer import PoseAnalyzer
from core.video_processor import VideoProcessor

processor = VideoProcessor(PoseAnalyzer(angle_threshold=90))
results = {}

for video in Path('inputs').glob('*.mp4'):
    print(f"Processing {video.name}...")
    result = processor.process_video(
        str(video),
        f'outputs/{video.stem}_analyzed.mp4'
    )
    results[video.name] = result.efficiency

# Print summary
for name, eff in sorted(results.items(), key=lambda x: x[1], reverse=True):
    print(f"{name}: {eff:.2f}%")
```

### Custom Analysis Workflow
```python
from core.pose_analyzer import PoseAnalyzer
import cv2
import mediapipe as mp

# Create custom analyzer
analyzer = PoseAnalyzer(angle_threshold=85)
pose = mp.solutions.pose.Pose()

# Process video manually
cap = cv2.VideoCapture('input.mp4')
good, bad = 0, 0

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    
    processed, is_good, angles = analyzer.analyze_frame(frame, pose)
    if angles:
        good += is_good
        bad += not is_good
    
    # Custom logic here
    if angles:
        print(f"Right: {angles[0]:.1f}°, Left: {angles[1]:.1f}°")

cap.release()
print(f"Efficiency: {good/(good+bad)*100:.2f}%")
```

## 📚 Further Reading

- **Full Documentation**: `README.md`
- **Architecture Details**: `docs/ARCHITECTURE.md`
- **Migration Guide**: `docs/MIGRATION.md`
- **Complete Changes**: `docs/RESTRUCTURING_SUMMARY.md`

## 🆘 Getting Help

1. Check error messages in terminal
2. Read documentation in `docs/`
3. Review `scripts/example_usage.py`
4. Check MediaPipe documentation: https://google.github.io/mediapipe/
5. Check Streamlit docs: https://docs.streamlit.io/

## 🎓 Learning Path

1. ✅ Run the Streamlit app
2. ✅ Process a sample video
3. ✅ Read `docs/ARCHITECTURE.md`
4. ✅ Run `scripts/example_usage.py`
5. ✅ Modify angle threshold
6. ✅ Customize colors
7. ✅ Add new features

---

**Pro Tip**: Keep this file open in a separate tab for quick reference!
