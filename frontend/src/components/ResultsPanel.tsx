import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, Pause, Play } from 'lucide-react'
import { getVideoUrl } from '../api'
import StatTile from './StatTile'
import { angleStatus, gradeLabel, hipStatus, STATUS_HEX, STATUS_TEXT } from '../utils/metrics'
import type { AnalysisResult, PoseEntry, VideoInfo } from '../types'

const Skeleton3D = lazy(() => import('./Skeleton3D'))

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
  const { label: grade, status: gradeStatus } = gradeLabel(result.efficiency)
  const gradeColor = STATUS_TEXT[gradeStatus]

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

  // ── Keyboard: Space toggles playback, ←/→ step one frame.
  //    Skipped when a control has focus so it keeps its native key handling.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLButtonElement) return
      if (e.key === ' ') {
        e.preventDefault()
        isPlaying ? stopPlay() : startPlay()
      } else if (e.key === 'ArrowLeft') {
        handleScrub(Math.max(currentFrame - 1, 0))
      } else if (e.key === 'ArrowRight') {
        handleScrub(Math.min(currentFrame + 1, totalFrames - 1))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

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
          <div className="label mb-1">Efficiency</div>
          <div className="flex items-baseline gap-3">
            <span className={`font-display text-5xl font-bold tabular-nums ${gradeColor}`}>
              {result.efficiency.toFixed(1)}%
            </span>
            <span className={`font-body text-base font-semibold ${gradeColor}`}>
              {grade}
            </span>
          </div>
          <div className="efficiency-bar w-48 mt-2">
            <div
              className="h-full transition-all"
              style={{ width: `${result.efficiency}%`, background: STATUS_HEX[gradeStatus] }}
            />
          </div>
        </div>

        <div className="ml-auto flex gap-2">
          <button className="btn-ghost" onClick={onReset}>
            <ArrowLeft size={16} aria-hidden />
            New video
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
            muted
          />
        </div>

        <div className="card overflow-hidden h-[340px] md:h-[380px]">
          {poseData.length > 0 ? (
            <Suspense fallback={<div className="h-full bg-cream/5 animate-pulse" />}>
              <Skeleton3D
                poseData={poseData}
                currentFrame={currentFrame}
                isGood={isGoodFrame}
              />
            </Suspense>
          ) : (
            <div className="flex items-center justify-center h-full text-muted text-sm">
              No pose data available
            </div>
          )}
        </div>
      </div>

      {/* Per-frame metrics */}
      {currentEntry && (
        <div className="card p-3 grid grid-cols-3 divide-x divide-navy-lighter text-center">
          <StatTile
            label="L arm"
            value={currentEntry[5] != null ? `${Math.round(currentEntry[5])}°` : '—'}
            status={angleStatus(currentEntry[5])}
          />
          <StatTile
            label="R arm"
            value={currentEntry[4] != null ? `${Math.round(currentEntry[4])}°` : '—'}
            status={angleStatus(currentEntry[4])}
          />
          <StatTile
            label="Hips"
            value={currentEntry[6] != null ? currentEntry[6].toFixed(2) : '—'}
            status={hipStatus(currentEntry[6])}
          />
        </div>
      )}

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
          <button className="btn-primary w-28" onClick={togglePlay}>
            {isPlaying ? <Pause size={16} aria-hidden /> : <Play size={16} aria-hidden />}
            {isPlaying ? 'Pause' : 'Play'}
          </button>
          <span className="text-muted text-xs font-body tabular-nums">
            {fmt(currentFrame)} / {fmt(totalFrames)}
          </span>
          <span className="text-xs font-body ml-auto">
            <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${isGoodFrame ? 'bg-success' : 'bg-danger'}`} />
            <span className="text-muted">{isGoodFrame ? 'Arms open' : 'Compressed'}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
