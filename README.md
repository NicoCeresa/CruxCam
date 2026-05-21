# CruxCam

A climbing efficiency analyzer that processes video through a pose detection pipeline and scores technique frame-by-frame.

## How it works

CruxCam uses MediaPipe to detect body landmarks on each frame of a climbing video. Angles are calculated at each elbow joint in **3D world space** (metres, hip-relative) and each frame is classified as **good** (arms extended) or **bad** (arms compressed). The final efficiency score is the percentage of good frames.

It also estimates the climber's **center of mass (CoM)** using biomechanically weighted body segments (head 8%, torso 50%, each arm 5%, each leg 16%), computed in 3D world space and smoothed with an exponential moving average.

**Visual indicators in the output video:**
- Yellow dots — detected body landmarks
- Green skeleton — good arm position (arms extended)
- Red skeleton — poor arm position (arms compressed)
- Blue dot — smoothed center of mass (labeled with depth)
- On-screen panel — live efficiency %, progress bar, and frame counts

## Architecture

```
React frontend → FastAPI → Celery worker → Redis
```

- **React** (`frontend/`) — upload, trim, polling, results with interactive 3D viewer
- **FastAPI** (`api/main.py`) — REST endpoints: `/info`, `/upload`, `/status/{id}`, `/result/{id}`, `/video/{id}`, `/sample/*`
- **Celery** (`api/tasks.py`) — runs `VideoProcessor.process_video` in a worker process
- **Redis** — message broker and result backend

Video processing uses a producer-consumer threading pipeline inside the worker: a reader thread decodes frames into a queue, the main worker thread runs pose inference, and a writer thread encodes frames to disk — overlapping I/O with inference.

## Stack

- [MediaPipe](https://google.github.io/mediapipe/) — 3D pose estimation (world landmarks)
- [OpenCV](https://opencv.org/) — video I/O and frame annotation
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) — web frontend
- [Three.js](https://threejs.org/) + [@react-three/fiber](https://docs.pmnd.rs/react-three-fiber) — interactive 3D skeleton viewer
- [Tailwind CSS](https://tailwindcss.com/) — styling
- [FastAPI](https://fastapi.tiangolo.com/) — REST API
- [Celery](https://docs.celeryq.dev/) — async task queue
- [Redis](https://redis.io/) — broker and result backend

## Project structure

```
CruxCam/
├── frontend/                 # React + Vite frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts            # Typed wrappers for all API endpoints
│   │   ├── types.ts
│   │   └── components/
│   │       ├── Header.tsx
│   │       ├── UploadZone.tsx
│   │       ├── TrimControls.tsx
│   │       ├── ProcessingView.tsx
│   │       ├── ResultsPanel.tsx
│   │       └── Skeleton3D.tsx  # Three.js skeleton viewer
│   ├── index.html
│   └── package.json
├── api/
│   ├── celery_app.py         # Celery configuration
│   ├── main.py               # FastAPI endpoints
│   └── tasks.py              # process_video_task, serialization helpers
├── core/
│   ├── pose_analyzer.py      # Angle calculation, CoM, frame annotation
│   └── video_processor.py    # Threaded video pipeline, AnalysisResult
├── notebooks/
│   └── 01_test_models.ipynb
└── inputs/                   # Sample videos (gitignored)
```

## Setup

**Prerequisites:** Python 3.10+, Node.js 18+, Redis running locally

```bash
git clone https://github.com/NicoCeresa/CruxCam.git
cd CruxCam
pip install -r requirements.txt
cd frontend && npm install
```

## Running

Four processes, each in its own terminal:

```bash
# 1. Redis (if not already running as a service)
redis-server

# 2. FastAPI
uvicorn api.main:app --reload

# 3. Celery worker (--pool=solo required on macOS)
celery -A api.celery_app worker --loglevel=info --pool=solo

# 4. React frontend
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `CRUXCAM_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |
| `CRUXCAM_FILE_TTL` | `3600` | Seconds before temp files are cleaned up |
| `CRUXCAM_MAX_UPLOAD_MB` | `500` | Max upload size in MB |
| `CRUXCAM_RATE_LIMIT` | `10` | Max uploads per IP per minute |
| `CRUXCAM_SAMPLE_PATH` | `inputs/tomoa_outside.mp4` | Path to built-in sample video |

## Usage

1. Upload a climbing video (MP4, MOV, AVI, MKV) or check **Use sample video**
2. Adjust the arm angle threshold (default 90°) — frames where both elbows are below this angle count as compressed
3. Trim the clip using the range slider with live frame previews
4. Click **Analyze Footage**
5. View the annotated video alongside the interactive 3D skeleton — scrub or play both in sync, rotate the 3D view freely while playing

## Efficiency score

```
efficiency = (good_frames / total_frames) × 100
```

| Score | Label | Interpretation |
|---|---|---|
| 70%+ | Solid Form | Arms extended, skeleton bearing load efficiently |
| 50–69% | Needs Work | Reduce time pulling into the wall |
| <50% | Gripped | Compressed position most of the climb — focus on straight-arm hangs |

## Deployment

The frontend and backend deploy independently:

| Service | Platform |
|---|---|
| React frontend | Vercel or Netlify (`frontend/` as root) |
| FastAPI | Railway or Render |
| Celery worker | Railway or Render (second service, same repo) |
| Redis | Railway managed Redis or Redis Cloud |

Set `VITE_API_URL` to the deployed FastAPI URL in your frontend deploy environment.  
Set `CRUXCAM_ALLOWED_ORIGINS` to your frontend domain on the API server.

## Future work

- Video comparison mode — side-by-side analysis of two clips
- Instagram reel input
- Multi-climber tracking
- Progress tracking over time
- Hold detection via ICA to analyze hold usage patterns
