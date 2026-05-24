# CruxCam

A climbing efficiency analyzer that processes video through a pose detection pipeline and scores technique frame-by-frame.

## Features

- **Analyze** — upload a single clip, trim it, and get a frame-by-frame efficiency breakdown with an annotated video and interactive 3D skeleton viewer
- **Compare** — load two clips side by side, process them, and play both videos and skeletons in sync to spot differences in technique across climbs or sessions

## How it works

CruxCam uses MediaPipe to detect body landmarks on each frame of a climbing video. Angles are calculated at each elbow joint in **3D world space** (metres, hip-relative) and each frame is classified as **good** (arms extended) or **bad** (arms compressed). The final efficiency score is the percentage of good frames.

It also estimates the climber's **center of mass (CoM)** using biomechanically weighted body segments (head 8%, torso 50%, each arm 5%, each leg 16%), computed in 3D world space and smoothed with an exponential moving average.

## Architecture

```
Vercel (React) → Railway (FastAPI + Redis)
```

- **React** (`frontend/`) — upload, trim, polling, results with interactive 3D skeleton viewer; two routes: `/analyze` and `/compare`
- **FastAPI** (`api/main.py`) — REST endpoints: `/info`, `/submit`, `/status/{id}`, `/result/{id}`, `/video/{id}`, `/sample/*`
- **ThreadPoolExecutor** (`api/tasks.py`) — runs `VideoProcessor.process_video` in a background thread (max 1 concurrent job to stay within Railway memory limits)
- **Redis** — persists job state (progress, results) across requests

Video processing uses a reader thread to overlap disk I/O with MediaPipe inference. Output is produced by ffmpeg stream-copying the original upload with the trim applied — no frames are decoded or re-encoded, keeping peak memory low.

## Stack

- [MediaPipe](https://google.github.io/mediapipe/) — 3D pose estimation (world landmarks, `model_complexity=0`)
- [OpenCV](https://opencv.org/) — video I/O
- [ffmpeg](https://ffmpeg.org/) — container remux and trim
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) — web frontend
- [React Router](https://reactrouter.com/) — client-side routing
- [Three.js](https://threejs.org/) + [@react-three/fiber](https://docs.pmnd.rs/react-three-fiber) — interactive 3D skeleton viewer
- [Tailwind CSS](https://tailwindcss.com/) — styling
- [FastAPI](https://fastapi.tiangolo.com/) — REST API
- [Redis](https://redis.io/) — job state store
- [Docker](https://www.docker.com/) — containerised backend deployment

## Project structure

```
CruxCam/
├── frontend/                 # React + Vite frontend (deployed to Vercel)
│   └── src/
│       ├── api.ts            # Typed wrappers for all API endpoints
│       ├── types.ts
│       ├── pages/
│       │   ├── HomePage.tsx
│       │   ├── AnalyzePage.tsx
│       │   └── ComparePage.tsx
│       └── components/
│           ├── UploadZone.tsx
│           ├── TrimControls.tsx
│           ├── CompareColumn.tsx
│           ├── ResultsPanel.tsx
│           └── Skeleton3D.tsx  # Three.js skeleton viewer
├── api/
│   ├── main.py               # FastAPI endpoints + ThreadPoolExecutor job submission
│   └── tasks.py              # process_video, serialize/deserialize helpers
├── core/
│   ├── pose_analyzer.py      # Angle calculation, CoM, frame classification
│   └── video_processor.py    # Threaded inference pipeline, AnalysisResult
├── inputs/                   # Sample videos (gitignored except .gitkeep)
├── Dockerfile
├── docker-compose.yml        # Local development (API + Redis)
├── start.sh                  # Entrypoint: exec uvicorn
└── requirements.txt
```

## Setup

**Prerequisites:** Python 3.11+, Node.js 18+, Docker (recommended)

```bash
git clone https://github.com/NicoCeresa/CruxCam.git
cd CruxCam
pip install -r requirements.txt
cd frontend && npm install
```

## Running locally

**Option A — Docker (recommended)**

```bash
docker compose up --build
cd frontend && npm run dev
```

**Option B — manually**

```bash
# 1. Redis
redis-server

# 2. FastAPI (background threads handle processing — no separate worker needed)
uvicorn api.main:app --reload

# 3. React frontend
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

**Analyze**
1. Upload a climbing video (MP4, MOV, AVI, MKV, WebM) or click **Use sample video**
2. Trim the clip using the dual-handle slider — start and end frame thumbnails update live
3. Click **Analyze Footage** and wait for processing
4. View the efficiency score, annotated video, and interactive 3D skeleton — scrub or play, rotate the 3D view freely

**Compare**
1. Drop a video into each column (Video A and Video B)
2. Trim each clip independently
3. Click **Analyze Footage** — both jobs run and results appear as each finishes
4. Use the shared Play/Pause button to watch both videos and skeletons in sync

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

**Frontend → Vercel**
- Connect GitHub repo, set root directory to `frontend`
- Add env var: `VITE_API_URL=https://your-railway-url.up.railway.app`

**Backend → Railway**
- Deploy from GitHub repo (auto-detects `Dockerfile`)
- Add managed Redis service, set `REDIS_URL`
- Add env var: `CRUXCAM_ALLOWED_ORIGINS=https://your-vercel-url.vercel.app`
- `start.sh` runs a single uvicorn process; background threads handle video processing

## Future work

- Instagram reel input
- Multi-climber tracking
- Progress tracking over time
- Hold detection via ICA to analyze hold usage patterns
