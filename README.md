# CruxCam

A climbing efficiency analyzer that processes video through a pose detection pipeline and scores technique frame-by-frame.

## How it works

CruxCam uses MediaPipe to detect body landmarks on each frame of a climbing video. Angles are calculated at each elbow joint in **3D world space** (metres, hip-relative) and each frame is classified as **good** (arms extended) or **bad** (arms compressed). The final efficiency score is the percentage of good frames.

It also estimates the climber's **center of mass (CoM)** using biomechanically weighted body segments (head 8%, torso 50%, each arm 5%, each leg 16%), computed in 3D world space and smoothed with an exponential moving average to reduce jitter.

**Visual indicators in the output video:**
- Yellow dots — detected body landmarks
- Green skeleton — good arm position
- Red skeleton — poor arm position
- Blue dot — smoothed center of mass (labeled with depth in 3D mode)
- On-screen panel — live efficiency %, progress bar, and frame counts

**Results tab:**
- Efficiency score and frame counts
- Side-by-side annotated video frame + interactive 3D skeleton viewer
- Scrubable frame slider and play/pause, synchronized across both panels
- CoM path trace across all frames in the 3D viewer
- Download button for the processed video

## Architecture

The app is split into a Streamlit frontend and an async backend.

```
Browser (Streamlit) → FastAPI → Celery worker → Redis
```

- **Streamlit** (`app.py`) handles upload, polls for job status, and renders results
- **FastAPI** (`api/main.py`) exposes REST endpoints: `/info`, `/upload`, `/status/{id}`, `/result/{id}`
- **Celery** (`api/tasks.py`) runs `VideoProcessor.process_video` in a worker process
- **Redis** acts as the message broker and result store

Video processing uses a producer-consumer threading pipeline inside the worker: a reader thread decodes frames into a queue, the main worker thread runs pose inference, and a writer thread encodes frames to disk — overlapping I/O with inference.

## Stack

- [MediaPipe](https://google.github.io/mediapipe/) — 3D pose estimation (world landmarks)
- [OpenCV](https://opencv.org/) — video I/O and frame annotation
- [Streamlit](https://streamlit.io/) — web UI
- [Plotly](https://plotly.com/python/) — interactive 3D skeleton viewer
- [FastAPI](https://fastapi.tiangolo.com/) — REST API
- [Celery](https://docs.celeryq.dev/) — async task queue
- [Redis](https://redis.io/) — broker and result backend

## Project structure

```
CruxCam/
├── app.py                    # Streamlit frontend
├── api/
│   ├── __init__.py
│   ├── celery_app.py         # Celery configuration
│   ├── main.py               # FastAPI endpoints
│   └── tasks.py              # process_video_task, serialization helpers
├── core/
│   ├── pose_analyzer.py      # Angle calculation, CoM, frame annotation
│   └── video_processor.py    # Threaded video pipeline, AnalysisResult
├── notebooks/
│   └── 01_test_models.ipynb
├── uploads/                  # Uploaded videos (gitignored)
├── outputs/                  # Processed videos (gitignored)
└── inputs/                   # Sample videos (gitignored)
```

## Setup

**Prerequisites:** Python 3.10+, Redis running locally (or set `REDIS_URL`)

```bash
git clone https://github.com/NicoCeresa/CruxCam.git
cd CruxCam
pip install -r requirements.txt
```

## Running

Four processes, each in its own terminal:

```bash
# 1. Redis (if not already running as a service)
redis-server

# 2. FastAPI
uvicorn api.main:app --reload

# 3. Celery worker
celery -A api.celery_app worker --loglevel=info

# 4. Streamlit
streamlit run app.py
```

**Environment variables (optional):**

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `CRUXCAM_API_URL` | `http://localhost:8000` | FastAPI base URL |
| `CRUXCAM_UPLOAD_DIR` | `uploads/` | Where to store uploaded videos |
| `CRUXCAM_OUTPUT_DIR` | `outputs/` | Where to store processed videos |

## Usage

1. Upload a climbing video (MP4, MOV, AVI, MKV) or check **Use sample video**
2. Adjust settings in the sidebar — arm angle threshold (default 90°) and 3D mode toggle
3. Click **Process video**
4. View results in the **Results** tab

## Efficiency score

```
efficiency = (good_frames / total_frames) × 100
```

| Score | Interpretation |
|---|---|
| 70%+ | Good form — arms extended, skeleton bearing load |
| 50–69% | Room to improve — reduce time pulling into the wall |
| <50% | Compressed position most of the climb — focus on straight-arm hangs |

## Future work

- Instagram reel input
- Multi-climber tracking
- Progress tracking over time
- Hold detection via ICA to analyze hold usage patterns
