import { forwardRef, lazy, Suspense, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { getResult, getStatus, getVideoInfo, getVideoUrl, uploadVideo } from '../api'
import TrimControls from './TrimControls'
import { isToooDark } from '../utils/checkBrightness'
import type { AnalysisResult, PoseEntry, VideoInfo } from '../types'

const Skeleton3D = lazy(() => import('./Skeleton3D'))

const POLL_MESSAGES = [
  'Reading the route…',
  'Analyzing movement…',
  'Mapping your beta…',
  'Calculating efficiency…',
  'Processing footage…',
  'Tracking landmarks…',
]

function gradeLabel(efficiency: number): { label: string; color: string } {
  if (efficiency >= 70) return { label: 'Solid Form', color: 'text-forest-light' }
  if (efficiency >= 50) return { label: 'Needs Work', color: 'text-yellow-400' }
  return                       { label: 'Gripped',    color: 'text-red-400' }
}

type Phase = 'upload' | 'processing' | 'results'

const ACCEPT = '.mp4,.mov,.avi,.mkv,video/*'

export interface CompareColumnHandle {
  submit: () => void
}

interface Props {
  label: string
  sharedPlaying: boolean
  onPause: () => void
  onResultsReady: () => void
  onColumnReset: () => void
  onReadyChange: (ready: boolean) => void
}

const CompareColumn = forwardRef<CompareColumnHandle, Props>(function CompareColumn({
  label,
  sharedPlaying,
  onPause,
  onResultsReady,
  onColumnReset,
  onReadyChange,
}, ref) {
  // Lifecycle
  const [phase, setPhase]   = useState<Phase>('upload')
  const [file, setFile]     = useState<File | null>(null)
  const [info, setInfo]     = useState<VideoInfo | null>(null)
  const [jobId, setJobId]   = useState<string | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)

  // Upload
  const [, setLoading]                       = useState(false)
  const [error, setError]                   = useState<string | null>(null)
  const [darkWarning, setDarkWarning]       = useState(false)
  const [dragging, setDragging]             = useState(false)
  const [angleThreshold, setAngleThreshold] = useState(90)
  const [trimStart, setTrimStart]           = useState(0)
  const [trimEnd, setTrimEnd]               = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  // Processing
  const [progress, setProgress]     = useState(0)
  const [statusText, setStatusText] = useState('Waiting for worker…')

  // Playback
  const [currentFrame, setCurrentFrame] = useState(0)
  const videoRef = useRef<HTMLVideoElement>(null)
  const rafRef   = useRef<number | null>(null)

  const safeFps = Math.max(info?.fps ?? 30, 1)

  // ── Upload ────────────────────────────────────────────────────────────────

  async function loadFile(f: File) {
    setFile(f)
    setError(null)
    setDarkWarning(false)
    setLoading(true)
    try {
      const i = await getVideoInfo(f)
      setInfo(i)
      setTrimStart(0)
      setTrimEnd(i.total_frames - 1)
      const dark = await isToooDark(i.preview_id, i.total_frames)
      setDarkWarning(dark)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to read video')
      setFile(null)
      setInfo(null)
    } finally {
      setLoading(false)
    }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) loadFile(f)
  }, [])

  async function handleSubmit() {
    if (!file || !info || phase !== 'upload') return
    setError(null)
    setLoading(true)
    try {
      const id = await uploadVideo(file, info.preview_id, angleThreshold, trimStart, trimEnd)
      setJobId(id)
      setPhase('processing')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  useImperativeHandle(ref, () => ({ submit: handleSubmit }))

  // Notify parent when this column has a file ready to submit
  useEffect(() => {
    onReadyChange(phase === 'upload' && !!file && !!info)
  }, [phase, file, info])

  function reset() {
    if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
    videoRef.current?.pause()
    setPhase('upload')
    setFile(null)
    setInfo(null)
    setJobId(null)
    setResult(null)
    setProgress(0)
    setCurrentFrame(0)
    setError(null)
    onColumnReset()
  }

  // ── Processing (inline polling) ───────────────────────────────────────────

  useEffect(() => {
    if (phase !== 'processing' || !jobId) return

    let stopped = false
    let lastProgress = -1
    let lastProgressAt = Date.now()
    let networkErrors = 0
    const STALL_MS = 60_000
    let msgIdx = 0

    const msgId = setInterval(() => {
      msgIdx = (msgIdx + 1) % POLL_MESSAGES.length
      setStatusText(POLL_MESSAGES[msgIdx])
    }, 2500)

    const pollId = setInterval(async () => {
      if (stopped) return
      try {
        const status = await getStatus(jobId)
        if (stopped) return
        networkErrors = 0

        if (status.status === 'pending') {
          setStatusText('Waiting for worker…')
          lastProgressAt = Date.now()
          return
        }
        if (status.status === 'processing') {
          if (status.progress !== lastProgress) {
            lastProgress = status.progress
            lastProgressAt = Date.now()
          } else if (Date.now() - lastProgressAt > STALL_MS) {
            stopped = true
            clearInterval(pollId)
            clearInterval(msgId)
            setError('Processing stalled — try a shorter clip.')
            setPhase('upload')
            return
          }
          setProgress(status.progress)
          return
        }
        if (status.status === 'complete') {
          stopped = true
          clearInterval(pollId)
          clearInterval(msgId)
          setProgress(1)
          const res = await getResult(jobId)
          setResult(res)
          setPhase('results')
          onResultsReady()
          return
        }
        if (status.status === 'failed') {
          stopped = true
          clearInterval(pollId)
          clearInterval(msgId)
          setError(status.error ?? 'Processing failed')
          setPhase('upload')
        }
      } catch {
        networkErrors++
        if (networkErrors >= 3) {
          stopped = true
          clearInterval(pollId)
          clearInterval(msgId)
          setError('Connection lost — check your network and try again.')
          setPhase('upload')
        }
      }
    }, 1000)

    return () => {
      stopped = true
      clearInterval(pollId)
      clearInterval(msgId)
    }
  }, [phase, jobId])

  // ── Respond to shared play/pause ──────────────────────────────────────────

  useEffect(() => {
    if (phase !== 'results') return
    const video = videoRef.current
    if (!video) return

    if (sharedPlaying) {
      video.play().catch(() => {})
      if (rafRef.current === null) {
        const tick = () => {
          const v = videoRef.current
          if (!v || v.paused || v.ended) { rafRef.current = null; return }
          setCurrentFrame(Math.round(v.currentTime * safeFps))
          rafRef.current = requestAnimationFrame(tick)
        }
        rafRef.current = requestAnimationFrame(tick)
      }
    } else {
      video.pause()
      if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
    }
  }, [sharedPlaying, phase, safeFps])

  // ── Scrubbing — seek immediately and tell parent to pause ─────────────────

  function handleScrub(frame: number) {
    videoRef.current?.pause()
    if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
    setCurrentFrame(frame)
    if (videoRef.current) videoRef.current.currentTime = frame / safeFps
    onPause()
  }

  // ── Cleanup on unmount ────────────────────────────────────────────────────

  useEffect(() => () => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
  }, [])

  // ── Derived ───────────────────────────────────────────────────────────────

  const poseData = result?.pose_data_3d ?? []
  const totalFrames = poseData.length > 0
    ? Math.max(...poseData.map(e => e[0])) + 1
    : (info?.total_frames ?? 0)

  const currentEntry: PoseEntry | undefined =
    poseData.find(e => e[0] === currentFrame) ??
    poseData.reduce<PoseEntry | undefined>((best, e) =>
      !best ? e : Math.abs(e[0] - currentFrame) < Math.abs(best[0] - currentFrame) ? e : best
    , undefined)
  const isGoodFrame = currentEntry?.[2] ?? true

  function fmt(frames: number) {
    const secs = frames / safeFps
    const m = Math.floor(secs / 60).toString().padStart(2, '0')
    const s = Math.floor(secs % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  // ── Upload phase ──────────────────────────────────────────────────────────

  if (phase === 'upload') {
    return (
      <div className="space-y-4">
        <div className="font-display tracking-widest uppercase text-cream/40 text-xs">{label}</div>

        <div
          className={`card p-6 text-center cursor-pointer transition-colors duration-150
            ${dragging ? 'border-terracotta bg-terracotta/5' : 'hover:border-cream/30'}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={e => e.target.files?.[0] && loadFile(e.target.files[0])}
          />
          <svg viewBox="0 0 120 70" className="w-16 h-10 mx-auto mb-3 text-cream/20">
            <path d="M5,70 L45,8 L65,35 L85,5 L115,70 Z" fill="currentColor" />
          </svg>
          {file ? (
            <div className="space-y-1">
              <p className="text-cream font-body font-medium text-sm truncate">{file.name}</p>
              {info && (
                <p className="text-cream/40 text-xs">
                  {info.total_frames} frames · {info.fps} fps
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-cream/70 font-body text-sm">Drop footage here or click to browse</p>
              <p className="text-cream/30 text-xs tracking-wider uppercase">MP4 · MOV · AVI · MKV</p>
            </div>
          )}
        </div>

        {info && (
          <div className="card p-4 space-y-4">
            <div className="flex items-center justify-between gap-4">
              <label className="text-xs tracking-wider uppercase text-cream/50">Arm Angle</label>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min={30} max={120} step={5}
                  value={angleThreshold}
                  onChange={e => setAngleThreshold(Number(e.target.value))}
                  className="w-24 accent-terracotta"
                />
                <span className="font-display text-xl text-terracotta w-10 text-right">
                  {angleThreshold}°
                </span>
              </div>
            </div>
            <div className="border-t border-navy-lighter" />
            <TrimControls
              previewId={info.preview_id}
              totalFrames={info.total_frames}
              fps={info.fps}
              start={trimStart}
              end={trimEnd}
              onChange={(s, e) => { setTrimStart(s); setTrimEnd(e) }}
            />
          </div>
        )}

        {darkWarning && (
          <div className="border border-yellow-500/40 bg-yellow-500/10 px-3 py-2 text-yellow-400 text-xs font-body flex items-start gap-2">
            <span className="flex-shrink-0">⚠</span>
            <span>This video appears dark — pose detection may be less accurate. Improving lighting before recording will give better results.</span>
          </div>
        )}

        {error && <p className="text-red-400 text-xs text-center">{error}</p>}
      </div>
    )
  }

  // ── Processing phase ──────────────────────────────────────────────────────

  if (phase === 'processing') {
    return (
      <div className="space-y-4">
        <div className="font-display tracking-widest uppercase text-cream/40 text-xs">{label}</div>
        <div className="card p-6 space-y-6">
          <div className="text-center space-y-1">
            <h3 className="font-display text-2xl tracking-widest uppercase text-cream">On the Wall</h3>
            <p className="text-cream/50 text-sm">{statusText}</p>
          </div>
          <div className="space-y-2">
            <div className="efficiency-bar">
              <div
                className="h-full bg-terracotta transition-all duration-200 ease-out"
                style={{ width: `${Math.round(progress * 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-cream/30 font-body">
              <span>{Math.round(progress * 100)}%</span>
              <span>Analyzing frames</span>
            </div>
          </div>
          <div className="flex justify-center">
            <svg viewBox="0 0 60 60" className="w-10 h-10 text-brown-light animate-spin" style={{ animationDuration: '3s' }}>
              <circle cx="30" cy="30" r="20" stroke="currentColor" strokeWidth="3" fill="none" strokeDasharray="30 95" strokeLinecap="round" />
              <circle cx="30" cy="30" r="12" stroke="currentColor" strokeWidth="2" fill="none" strokeDasharray="18 57" strokeLinecap="round" strokeDashoffset="20" />
            </svg>
          </div>
        </div>
      </div>
    )
  }

  // ── Results phase ─────────────────────────────────────────────────────────

  const { label: grade, color: gradeColor } = gradeLabel(result!.efficiency)
  const videoUrl = getVideoUrl(jobId!)

  return (
    <div className="space-y-4">

      {/* File name header */}
      <div className="flex items-baseline gap-3">
        <span className="font-display tracking-widest uppercase text-cream/40 text-xs flex-shrink-0">
          {label}
        </span>
        <span className="text-cream font-body text-sm font-medium truncate">{file?.name}</span>
      </div>

      {/* Score bar */}
      <div className="card p-4 flex items-center gap-4">
        <div>
          <div className="text-cream/40 text-xs tracking-widest uppercase mb-0.5">Efficiency</div>
          <div className="flex items-baseline gap-2">
            <span className={`font-display text-4xl ${gradeColor}`}>
              {result!.efficiency.toFixed(1)}%
            </span>
            <span className={`font-display text-sm tracking-widest uppercase ${gradeColor}`}>
              {grade}
            </span>
          </div>
        </div>
        <div className="flex gap-5 ml-2">
          <div>
            <div className="text-forest-light font-display text-xl">{result!.good_frames}</div>
            <div className="text-cream/40 text-xs tracking-wider uppercase">Open</div>
          </div>
          <div>
            <div className="text-red-400 font-display text-xl">{result!.bad_frames}</div>
            <div className="text-cream/40 text-xs tracking-wider uppercase">Compressed</div>
          </div>
        </div>
        <button className="btn-ghost text-xs ml-auto" onClick={reset}>Reset</button>
      </div>

      {/* Video */}
      <div className="card overflow-hidden aspect-video">
        <video
          ref={videoRef}
          src={`${videoUrl}#t=0.001`}
          className="w-full h-full object-contain bg-black"
          preload="auto"
          playsInline
        />
      </div>

      {/* 3D Skeleton */}
      <div className="card overflow-hidden h-64">
        {poseData.length > 0 ? (
          <Suspense fallback={
            <div className="flex items-center justify-center h-full text-cream/30 text-sm">
              Loading 3D viewer…
            </div>
          }>
            <Skeleton3D poseData={poseData} currentFrame={currentFrame} isGood={isGoodFrame} />
          </Suspense>
        ) : (
          <div className="flex items-center justify-center h-full text-cream/30 text-sm">
            No pose data
          </div>
        )}
      </div>

      {/* Per-column scrubber and frame indicator */}
      <div className="card p-4 space-y-3">
        <input
          type="range"
          min={0}
          max={Math.max(totalFrames - 1, 0)}
          value={currentFrame}
          onChange={e => handleScrub(Number(e.target.value))}
          className="w-full accent-terracotta"
        />
        <div className="flex items-center justify-between">
          <span className="text-cream/40 text-xs font-body tabular-nums">
            {fmt(currentFrame)} / {fmt(totalFrames)}
          </span>
          <span className="text-xs font-body flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${isGoodFrame ? 'bg-forest-light' : 'bg-red-400'}`} />
            <span className="text-cream/50">{isGoodFrame ? 'Arms open' : 'Compressed'}</span>
          </span>
        </div>
      </div>

    </div>
  )
})

export default CompareColumn
