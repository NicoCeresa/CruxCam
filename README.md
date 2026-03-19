# CruxCam

A Streamlit web app that analyzes climbing videos using pose detection to score technique efficiency.

## How it works

CruxCam uses MediaPipe to detect body landmarks on each frame of a climbing video. It calculates the angle at each elbow joint and classifies the frame as **good** (arms extended) or **bad** (arms bent/compressed). The final efficiency score is the percentage of good frames.

**Visual indicators in the output video:**
- Yellow dots — detected body landmarks
- Green connections — good arm position
- Red connections — poor arm position
- On-screen panel — live efficiency %, progress bar, and frame counts

## Stack

- [MediaPipe](https://google.github.io/mediapipe/) — pose estimation
- [OpenCV](https://opencv.org/) — video I/O and frame annotation
- [Streamlit](https://streamlit.io/) — web UI

## Project structure

```
CruxCam/
├── app.py                    # Streamlit entry point
├── core/
│   ├── pose_analyzer.py      # Angle calculation, landmark drawing, overlay
│   └── video_processor.py    # Video I/O, frame loop, progress callback
├── notebooks/
│   └── 01_test_models.ipynb  # Development notebook
├── inputs/                   # Input videos (gitignored)
└── outputs/                  # Processed videos (gitignored)
```

## Setup

```bash
git clone https://github.com/NicoCeresa/CruxCam.git
cd CruxCam
pip install streamlit opencv-python mediapipe numpy
streamlit run app.py
```

## Usage

1. Upload a climbing video (MP4, MOV, AVI, MKV) or use the sample
2. Adjust the arm angle threshold in the sidebar (default 90°)
3. Click **Process Video**
4. View results in the **Results** tab — efficiency score, annotated video, download

## Efficiency score

```
efficiency = (good_frames / total_frames) × 100
```

| Score | Interpretation |
|-------|---------------|
| 70%+ | Excellent form |
| 50–69% | Room for improvement |
| <50% | Focus on arm extension |

## Future work

- Instagram reel input
- 3D pose estimation
- Multi-climber tracking
- Progress tracking over time
- Use Independent Component Analysis (ICA) to extract holds from the wall and analyze hold usage patterns
