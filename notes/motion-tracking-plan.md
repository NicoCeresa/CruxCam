# Plan: Camera-motion detection & wall-relative climber motion

## Goal

Measure how the climber moves **relative to the wall**, not relative to the camera frame.

- Tripod clips: the camera frame already is the wall frame. The job is to confirm that automatically.
- Handheld clips: estimate the camera motion with Lucas-Kanade tracking plus a RANSAC homography, then remove it.

New metrics come out of this: hip path, distance climbed, speed, still/rest periods, and later limb-on-hold contacts.

## Assumptions (confirm or correct)

1. Most clips are tripod. Handheld must work "reasonably", not perfectly.
2. Backend stays CPU-only on Railway, with one or two jobs at a time. **Nothing before Phase 5 may add torch or a model download.** OpenCV built-ins only.
3. The wall is roughly planar within a short window, so a homography is the right background-motion model (`papers/Moving-Objects-Detection-Moving-Camera-Review.pdf`, `papers/SkiTraVis-...pdf`).
4. Wall-relative distances are in **torso lengths**, plus approximate metres from MediaPipe's world torso length. They are only approximate, because the camera is not exactly front-on.

---

## Order of work

Each step ends green: tests pass and existing results are unchanged unless the step says otherwise.

| # | Step | Changes results? | Verify |
|---|---|---|---|
| 0 | **Test harness:** pytest, characterization tests, synthetic-video generator, CI | No | Tests pass on current `main` |
| 1 | **Backend refactor:** config, job store, preview store, routes, `FrameResult`, constructor/`Depends` injection | No | Characterization tests unchanged |
| 2 | **Small fixes:** `/info` blocking the event loop; EMA updated only on inference frames; round serialized floats | Yes (EMA, rounding) | Re-pin expected values in a separate commit with an explanation |
| 3 | **`CameraMotion`:** sparse pyramidal LK + RANSAC homography, single pass | No (new fields only) | Synthetic camera-motion tests + real-clip eval script |
| 4 | **Wall-relative motion:** `motion_metrics`, API `camera_mode`, payload | No (new fields only) | Synthetic path/rest tests, serialization tests |
| 5 | **Frontend:** camera badge, mode control, wall-pinned hip trail, speed tile, moving/still timeline, summary card | — | `npm run build` + manual check on tripod and handheld clips |
| 6 | **LK extensions (pick per value):** landmark gap-filling, limb-on-hold contacts, residual-flow climber mask | Some | See "LK extensions" |
| 7 | **Learned trackers (spike):** RAFT / CoTracker3 | — | Only if a GPU worker exists |
| — | **Wall-angle spike** (Depth Pro + RANSAC plane) | — | Independent; decision gate below |

---

## Step 0 — Test harness

- `pytest` + `tests/` (there are no tests today).
- **Characterization tests:** run the current pipeline on a short committed clip (a few seconds, small resolution). Pin efficiency, angles, plane fields and the serialized JSON shape.
- **API tests:** FastAPI `TestClient` with the job store overridden by an in-memory one, so no Redis is needed.
- **`tests/synthetic.py`:**
  - a procedural textured "wall"
  - an optional coloured blob "climber" on a known path
  - camera motion from a known sequence of homographies (none / pan / shake / zoom)
  - written with `cv2.VideoWriter` so compression artifacts are realistic
- **Reference real clips:** 6–10 clips in `inputs/` (gitignored), labelled in `tests/reference_clips.json`. Include at least 2 handheld clips.
- **GitHub Actions:** `pytest` (with `libgl1` and `ffmpeg` installed) plus `npm ci && npm run build`. The real-clip eval stays local.

## Step 1 — Backend refactor

```
api/
  main.py       create app, CORS, include router
  config.py     Settings: all CRUXCAM_* env vars
  deps.py       get_settings / get_job_store / get_preview_store (FastAPI Depends)
  jobs.py       JobStore (Redis), submit, run, serialize   (absorbs tasks.py)
  previews.py   PreviewStore: temp files, scaling, cleanup, thumbnails
  routes.py     endpoints; sample and upload share one code path
core/
  results.py         FrameResult + AnalysisResult dataclasses (replaces the positional tuple internally)
  pose_analyzer.py   measurements only (drawing code removed: unused by the app, and the notebook doesn't import core/)
  video_processor.py takes PoseAnalyzer (and later CameraMotion) through its constructor
```

- The wire format is unchanged: `serialize_result` converts `FrameResult` back into today's positional list, so the frontend needs no changes.
- Injection matters for this feature in particular. **MediaPipe will not detect a synthetic blob as a person**, so pipeline tests on synthetic video inject a `StubAnalyzer` that reports the blob's known position as the hip.
- No DI framework, no service layer, no multi-file routes package.

## Step 3 — `CameraMotion` (single pass)

New module `core/camera_motion.py`. It holds state across frames like `PoseAnalyzer` and has `reset()`, `update()` and `summary()`. It knows nothing about MediaPipe, Redis or HTTP.

Per inference frame, called from `VideoProcessor` right after pose analysis:
1. Convert to grayscale and downscale to about 480 px wide.
2. Choose features with `goodFeaturesToTrack`, masking out the climber with the current frame's landmark bounding box padded by about 20%. Re-detect features when fewer than about 100 survive.
3. Track with `calcOpticalFlowPyrLK` from the previous frame to this one and back again. Drop tracks whose forward-backward error is above 1 px.
4. `findHomography(..., cv2.RANSAC, 2.0)`. Record the inlier count and ratio.
5. Chain the result to the current **keyframe**. Start a new keyframe when inliers drop below a threshold or after N frames, so drift stays bounded.

After the loop, `summary()` classifies the clip:
- `tripod` if the 90th-percentile corner displacement per frame is under T px (start T = 1.0; tune on real clips).
- `handheld` otherwise.
- `uncertain` if fewer than 50% of frame pairs have enough inliers. Fall back to tripod behaviour and flag it.

For tripod clips, discard the homographies and use the identity, so wall coordinates = pixel coordinates.

A `camera_mode` of `tripod` or `handheld` overrides the classification. `tripod` also skips tracking entirely.

**Why single pass rather than a sampling pre-pass:** it needs no second video read, the climber mask comes free from the same frame's pose result, and there is less code. **Risk:** tripod clips pay for tracking. Measure in Step 0; the budget is ≤ 10% slower. If it doesn't fit, fall back to sampling about 30 frame pairs first.

## Step 4 — Wall-relative motion

New module `core/motion_metrics.py`: pure functions over arrays, no state and no OpenCV.
- Map the hip (2D pixels) into wall coordinates with each frame's homography.
- Scale by the median 2D torso length to get torso lengths; multiply by the median world torso length for approximate metres.
- **Metrics:**
  - smoothed hip speed
  - path length
  - vertical gain
  - still segments: speed below S torso-lengths/s for at least 0.5 s (start S = 0.15; tune)
  - % time moving
  - rest count and longest rest

**API:** `camera_mode = auto | tripod | handheld` on `/submit` and `/sample/upload`, default `auto`.

**Payload** (append only; `serialize_result` and `types.ts` change together):
- `PoseEntry` gains:
  - `[9] hip_wall_xy`
  - `[10] H_wall_to_frame` (9 floats, or null meaning identity)
  - `[11] hip_speed`
- New top-level fields:
  - `camera: { requested, detected, used, p90_motion_px, valid_pair_ratio }`
  - `motion_summary: { path_len, vertical_gain, pct_moving, rests: [[start, end], ...] }`

## Step 5 — UI

1. **Camera badge** in the results header: `Tripod · auto`, `Handheld · auto` or `Uncertain`.
2. **Mode control** `Auto | Tripod | Handheld` at the upload step, defaulting to Auto.
3. **Video overlay:** a `<canvas>` over the `<video>` drawing the last ~2 s of hip trail. Each point is projected through `H_wall_to_frame`, so the trail stays pinned to the wall. *This is the main visual check that compensation works.*
4. **Speed** `StatTile` in the per-frame row (shows `Still` below the threshold).
5. **Moving/still timeline strip** under the scrubber; clicking a rest jumps to it.
6. **Summary card:** distance, % moving, rests.
7. Compare page: badge and summary per column.

Follow `docs/visual-style.md`: lucide icons, status tokens, `StatTile`.

## Step 6 — LK extensions

All use OpenCV built-ins (CPU). Each is optional; ship them in order of value.

| Extension | Method | Value |
|---|---|---|
| **a. Limb-on-hold contacts** | LK-track a small patch at each wrist/ankle. A limb is "on a hold" when its patch moves with the wall homography (residual < ε px) for ≥ k frames | Contact timeline per limb. Also improves the existing contact plane, which currently fits all 4 limbs even mid-move, by using only limbs that are actually on holds |
| **b. Landmark gap-filling** | On frames skipped by `frame_skip`, carry the 2D landmarks forward with LK instead of reusing stale results | Smoother overlay and metrics at `frame_skip=2` without extra MediaPipe cost. 2D only; world landmarks stay stale |
| **c. Residual-flow climber mask** | Dense **DIS** optical flow at low resolution, minus the flow the homography predicts. Large residual = the climber | Better mask for feature selection than a padded box, plus a "movement energy / jerkiness" signal |
| **d. Robust sparse flow** | **RLOF** (`cv2.optflow`, needs `opencv-contrib-python`) as a drop-in for pyramidal LK if blur or lighting breaks tracking | Only if Step 3's real-clip eval shows LK failing |

## Step 7 — Learned trackers (spike, GPU-gated)

- **RAFT** (torchvision): dense flow robust to blur and large motion. Would replace DIS in (c).
- **CoTracker3:** long-range point tracking through occlusion. Would replace LK patch tracking in (a) and handle dynos and limbs hidden behind the body.
- **Go only if** a GPU worker exists, **and** the real-clip eval shows a clear failure that classic LK/DIS can't handle.

## Wall-angle spike (independent decision gate)

- Notebook: Depth Pro on a single frame, climber masked out, RANSAC plane fit, then the angle relative to gravity (assuming a level camera).
- Compare against known wall angles on 5 clips, and against CIMI4D if useful.
- **Go only if** error is ≤ 5° **and** there is a way to run it. Otherwise, fall back to a user-entered wall angle.

---

## Testing & verification summary

| Test | Pass criterion |
|---|---|
| Characterization (current pipeline) | Unchanged through Step 1 |
| Static synthetic clip (+ moving blob) | Detected `tripod`; p90 motion < 0.5 px |
| Pan / shake synthetic clip | Detected `handheld`; homography corner error < 1.5 px vs ground truth |
| Handheld + blob on known path (StubAnalyzer) | Wall-relative path within 5% of ground truth; drift < 2% over 300 frames |
| Rest detection on a synthetic speed profile | Rests found within ±3 frames |
| Limb-on-hold (6a) on synthetic: blob patch fixed to wall vs moving | Contacts found within ±3 frames |
| `serialize_result` round-trip | New fields present; null when not computed; old fields unchanged |
| Real-clip eval (`scripts/eval_motion.py`) | **100% of tripod clips detected as tripod**; debug video shows the trail pinned to the holds |
| Performance (60 s clip) | Tripod ≤ 10% slower, handheld ≤ 35% slower, peak memory +≤ 100 MB |
| Frontend | `npm run build` passes; manual check of badge, overlay, timeline; Compare page works with old cached results |

## Open questions

1. Which motion metrics matter most? (Path length, % moving, rests, speed.)
2. Should the camera-mode control be visible by default, or in an advanced area?
3. Do you have handheld clips for the reference set?
4. Is a GPU worker ever an option? This gates Step 7 and the wall-angle spike.

Resolved: the notebook doesn't import `core/`, so `PoseAnalyzer`'s drawing code is removed in Step 1.
