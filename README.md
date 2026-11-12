# CruxCam

A climbing efficiency analyzer that processes video through a pose detection pipeline and scores technique frame-by-frame.

## Features

- **Analyze** — upload a single clip, trim it, and get a frame-by-frame efficiency breakdown with an annotated video and interactive 3D skeleton viewer
- **Compare** — load two clips side by side, process them, and play both videos and skeletons in sync to spot differences in technique across climbs or sessions

## How it works

CruxCam uses MediaPipe to detect body landmarks on each frame of a climbing video. Angles are calculated at each elbow joint from the **2D image landmarks** (MediaPipe's 3D estimates are unreliable for unusual climbing poses) and each frame is classified as **good** (arms extended) or **bad** (arms compressed). The final efficiency score is the percentage of good frames.

It also estimates the climber's **center of mass (CoM)** using biomechanically weighted body segments (head 8%, torso 50%, each arm 5%, each leg 16%), computed in 3D world space and smoothed with an exponential moving average.

## Architecture

```
Vercel (React) → Hugging Face Space (FastAPI, Docker)
```

- **React** (`frontend/`) — upload, trim, polling, results with interactive 3D skeleton viewer; two routes: `/analyze` and `/compare`
- **FastAPI** (`api/routes.py`) — REST endpoints: `/info`, `/submit`, `/status/{id}`, `/result/{id}`, `/video/{id}`, `/sample/*`
- **ThreadPoolExecutor** (`api/deps.py`, `api/jobs.py`) — runs `VideoProcessor.process_video` in background threads (max 2 concurrent jobs, so Compare can process both clips)
- **Job store** (`api/jobs.py`) — job state (progress, results) in memory, expiring after `CRUXCAM_FILE_TTL`. Jobs run in-process, so a restart loses them either way; this assumes a single API instance

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
│   ├── main.py               # App setup: CORS + router
│   ├── config.py             # Settings from CRUXCAM_* env vars
│   ├── deps.py               # Shared services for Depends (job store, executor, previews, rate limiter)
│   ├── routes.py             # REST endpoints
│   ├── jobs.py               # Job state (in memory), submission, run, result serialization
│   └── previews.py           # Uploaded previews: temp files, 1080p scaling, thumbnails, cleanup
├── core/
│   ├── pose_analyzer.py      # MediaPipe Pose, angles, CoM, contact plane, frame classification
│   ├── results.py            # FrameResult / AnalysisResult dataclasses
│   └── video_processor.py    # Threaded inference pipeline
├── tests/                    # pytest: API, serialization, golden pipeline output, synthetic videos
├── inputs/                   # Sample videos (gitignored except .gitkeep)
├── Dockerfile
├── deploy/hf-space/README.md # Hugging Face Space config (deployed by .github/workflows/deploy-space.yml)
├── docker-compose.yml        # Local development (API)
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
# 1. FastAPI (background threads handle processing — no separate worker needed)
uvicorn api.main:app --reload

# 2. React frontend
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

**Tests**

```bash
pip install -r requirements-test.txt
pytest -rs                    # tests needing inputs/tomoa_outside.mp4 skip if it's missing
pytest --update-golden        # re-pin tests/golden/ after an intentional change to results
```

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `CRUXCAM_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |
| `CRUXCAM_FILE_TTL` | `3600` | Seconds before temp files are cleaned up |
| `CRUXCAM_MAX_UPLOAD_MB` | `500` | Max upload size in MB |
| `CRUXCAM_RATE_LIMIT` | `10` | Max requests per client per minute (uploads, sample loads and submits share one budget) |
| `CRUXCAM_PROXY_HOPS` | `0` | Reverse proxies in front of the API that append `X-Forwarded-For` (e.g. `1` behind a single proxy). The client address for rate limiting is taken from the right of that header; if it's present while this is `0`, the API logs a one-time warning |
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
- Add env var: `VITE_API_URL=https://<user>-<space>.hf.space`

**Backend → Hugging Face Space (Docker, free CPU tier)**
- Create a public Space with the Docker SDK (private Spaces require a Hugging Face login, so the frontend can't call them)
- In the GitHub repo add secret `HF_TOKEN` (a write token) and variable `HF_SPACE` (`<user>/<space>`). Pushes to `main` that touch the backend run `.github/workflows/deploy-space.yml`, which uploads the backend files plus `deploy/hf-space/README.md` (the Space config); run it by hand from the Actions tab for the first deploy
- In the Space settings add variables `CRUXCAM_ALLOWED_ORIGINS=https://your-vercel-url.vercel.app` and `CRUXCAM_PROXY_HOPS` (see the warning in the Space logs)
- `start.sh` runs a single uvicorn process; background threads handle video processing. Free Spaces sleep after about 48 hours without traffic, so the first request after that waits for a cold start

## Future work

- Instagram reel input
- Multi-climber tracking
- Progress tracking over time
- Hold detection via ICA to analyze hold usage patterns
