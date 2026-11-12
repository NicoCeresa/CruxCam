FROM python:3.11-slim

# System deps required by OpenCV and MediaPipe on Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# MediaPipe downloads its pose model into site-packages on first use. Do it now, as root,
# because the app runs as a non-root user that can't write there (and first jobs start faster).
RUN python -c "import mediapipe as mp; mp.solutions.pose.Pose(model_complexity=0).close()"

COPY api/   ./api/
COPY core/  ./core/
COPY inputs/ ./inputs/

COPY start.sh ./start.sh
RUN chmod +x start.sh

# Run as an unprivileged user: uploads are untrusted and decoded by ffmpeg/OpenCV.
# App files stay root-owned (read-only to the app); it only writes to the temp dir.
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
CMD ["./start.sh"]
