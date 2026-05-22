import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { getVideoUrl } from '../api'
import type { AnalysisResult, PoseEntry, VideoInfo } from '../types'

const Skeleton3D = lazy(() => import('./Skeleton3D'))

function gradeLabel(efficiency: number): { label: string; color: string } {
  if (efficiency >= 70) return { label: 'Solid Form', color: 'text-forest-light' }
  if (efficiency >= 50) return { label: 'Needs Work', color: 'text-yellow-400'   }
  return                       { label: 'Gripped',    color: 'text-red-400'      }
}

interface Props {
  result: AnalysisResult
  videoInfo: VideoInfo
  jobId: string
  onReset: () => void
}

export default function ResultsPanel({ result, videoInfo, jobId, onReset }: Props) {
  const { fps, total_frames } = videoInfo
  const safeFps = Math.max(fps, 1)
  const poseData = result.pose_data_3d ?? []
  const totalFrames = poseData.length > 0
    ? Math.max(...poseData.map(e => e[0])) + 1
    : total_frames

  const [currentFrame, setCurrentFrame] = useState(0)
  const [isPlaying, setIsPlaying]       = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const rafRef   = useRef<number | null>(null)

  const videoUrl = getVideoUrl(jobId)
  const { label: grade, color: gradeColor } = gradeLabel(result.efficiency)

  // ── Playback via requestAnimationFrame reading video.currentTime
  //    The video plays natively — no seeking during playback, no stalls.

  const stopPlay = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    rafRef.current = null
    videoRef.current?.pause()
    setIsPlaying(false)
  }, [])

  const startPlay = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    video.play().catch(() => {}) // ignore autoplay policy rejections

    setIsPlaying(true)

    const tick = () => {
      const v = videoRef.current
      if (!v || v.paused || v.ended) {
        setIsPlaying(false)
        return
      }
      setCurrentFrame(Math.round(v.currentTime * safeFps))
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
  }, [safeFps])

  function togglePlay() {
    isPlaying ? stopPlay() : startPlay()
  }

  // ── Scrubbing: only seek when paused (no seek during playback)
  function handleScrub(frame: number) {
    stopPlay()
    setCurrentFrame(frame)
    if (videoRef.current) {
      videoRef.current.currentTime = frame / safeFps
    }
  }

  // ── Stop if video ends naturally
  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    const onEnded = () => { setIsPlaying(false); rafRef.current = null }
    v.addEventListener('ended', onEnded)
    return () => v.removeEventListener('ended', onEnded)
  }, [])

  // ── Cleanup on unmount
  useEffect(() => () => stopPlay(), [stopPlay])

  // ── Current frame quality for skeleton colour
  const currentEntry: PoseEntry | undefined =
    poseData.find(e => e[0] === currentFrame) ??
    poseData.reduce<PoseEntry | undefined>((best, e) => {
      if (!best) return e
      return Math.abs(e[0] - currentFrame) < Math.abs(best[0] - currentFrame) ? e : best
    }, undefined)
  const isGoodFrame = currentEntry?.[2] ?? true

  function fmt(frames: number) {
    const secs = frames / safeFps
    const m = Math.floor(secs / 60).toString().padStart(2, '0')
    const s = Math.floor(secs % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  return (
    <div className="space-y-6">
      {/* Score header */}
      <div className="card p-5 flex flex-wrap items-center gap-6">
        <div>
          <div className="text-cream/40 text-xs tracking-widest uppercase mb-1">Efficiency</div>
          <div className="flex items-baseline gap-3">
            <span className={`font-display text-5xl font-700 ${gradeColor}`}>
              {result.efficiency.toFixed(1)}%
            </span>
            <span className={`font-display text-lg tracking-widest uppercase ${gradeColor}`}>
              {grade}
            </span>
          </div>
          <div className="efficiency-bar w-48 mt-2">
            <div
              className="h-full transition-all"
              style={{
                width: `${result.efficiency}%`,
                background: result.efficiency >= 70 ? '#3D7A37' : result.efficiency >= 50 ? '#FACC15' : '#EF4444',
              }}
            />
          </div>
        </div>

        <div className="flex gap-8 text-sm font-body">
          <div>
            <div className="text-forest-light font-semibold text-2xl font-display">{result.good_frames}</div>
            <div className="text-cream/40 text-xs tracking-wider uppercase">Arms Open</div>
          </div>
          <div>
            <div className="text-red-400 font-semibold text-2xl font-display">{result.bad_frames}</div>
            <div className="text-cream/40 text-xs tracking-wider uppercase">Compressed</div>
          </div>
        </div>

        <div className="ml-auto flex gap-2">
          <button className="btn-ghost text-xs" onClick={onReset}>
            ← New Video
          </button>
        </div>
      </div>

      {/* Video + 3D side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card overflow-hidden h-[300px] md:h-[380px]">
          <video
            ref={videoRef}
            src={`${videoUrl}#t=0.001`}
            className="w-full h-full object-contain bg-black"
            preload="auto"
            playsInline
          />
        </div>

        <div className="card overflow-hidden h-[340px] md:h-[380px]">
          {poseData.length > 0 ? (
            <Suspense fallback={<div className="flex items-center justify-center h-full text-cream/30 text-sm">Loading 3D viewer…</div>}>
              <Skeleton3D
                poseData={poseData}
                currentFrame={currentFrame}
                isGood={isGoodFrame}
              />
            </Suspense>
          ) : (
            <div className="flex items-center justify-center h-full text-cream/30 text-sm">
              No pose data available
            </div>
          )}
        </div>
      </div>

      {/* Scrubber + playback */}
      <div className="card p-4 space-y-3">
        <input
          type="range"
          min={0}
          max={totalFrames - 1}
          value={currentFrame}
          onChange={e => handleScrub(Number(e.target.value))}
          className="w-full accent-terracotta"
        />
        <div className="flex items-center gap-4">
          <button className="btn-primary px-6 py-2 text-xs" onClick={togglePlay}>
            {isPlaying ? '⏸ Pause' : '▶ Play'}
          </button>
          <span className="text-cream/40 text-xs font-body tabular-nums">
            {fmt(currentFrame)} / {fmt(totalFrames)}
          </span>
          <span className="text-xs font-body ml-auto">
            <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${isGoodFrame ? 'bg-forest-light' : 'bg-red-400'}`} />
            <span className="text-cream/50">{isGoodFrame ? 'Arms open' : 'Compressed'}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
