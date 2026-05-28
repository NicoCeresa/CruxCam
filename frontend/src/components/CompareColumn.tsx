import { forwardRef, lazy, Suspense, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { getVideoInfo, getVideoUrl } from '../api'
import TrimControls from './TrimControls'
import { isToooDark } from '../utils/checkBrightness'
import type { AnalysisResult, PoseEntry, VideoInfo } from '../types'

const Skeleton3D = lazy(() => import('./Skeleton3D'))

function angleColor(deg: number | null | undefined): string {
  if (deg == null) return 'text-cream/40'
  if (deg > 90) return 'text-forest-light'
  if (deg > 60) return 'text-yellow-400'
  return 'text-red-400'
}

function hipColor(dist: number | null | undefined): string {
  if (dist == null) return 'text-cream/40'
  if (dist < 0.3)  return 'text-forest-light'
  if (dist < 0.6)  return 'text-yellow-400'
  return 'text-red-400'
}

function gradeLabel(efficiency: number): { label: string; color: string } {
  if (efficiency >= 70) return { label: 'Solid Form', color: 'text-forest-light' }
  if (efficiency >= 50) return { label: 'Needs Work', color: 'text-yellow-400' }
  return                       { label: 'Gripped',    color: 'text-red-400' }
}

const ACCEPT = '.mp4,.mov,.avi,.mkv,video/*'

export interface ColumnUploadArgs {
  file: File
  info: VideoInfo
  angleThreshold: number
  trimStart: number
  trimEnd: number
}

export interface CompareColumnHandle {
  getUploadArgs: () => ColumnUploadArgs | null
  showResults: (result: AnalysisResult, jobId: string) => void
  reset: () => void
}

interface Props {
  label: string
  sharedPlaying: boolean
  onPause: () => void
  onColumnReset: () => void
  onReadyChange: (ready: boolean) => void
}

const CompareColumn = forwardRef<CompareColumnHandle, Props>(function CompareColumn({
  label,
  sharedPlaying,
  onPause,
  onColumnReset,
  onReadyChange,
}, ref) {
  type Phase = 'upload' | 'results'

  const [phase, setPhase]   = useState<Phase>('upload')
  const [file, setFile]     = useState<File | null>(null)
  const [info, setInfo]     = useState<VideoInfo | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [jobId, setJobId]   = useState<string | null>(null)

  const [loading, setLoading]               = useState(false)
  const [error, setError]                   = useState<string | null>(null)
  const [darkWarning, setDarkWarning]       = useState(false)
  const [dragging, setDragging]             = useState(false)
  const [trimStart, setTrimStart]           = useState(0)
  const [trimEnd, setTrimEnd]               = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

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

  useEffect(() => {
    onReadyChange(phase === 'upload' && !!file && !!info)
  }, [phase, file, info])

  // ── Imperative handle ─────────────────────────────────────────────────────

  useImperativeHandle(ref, () => ({
    getUploadArgs: () => {
      if (!file || !info || phase !== 'upload') return null
      return { file, info, angleThreshold: 90, trimStart, trimEnd }
    },
    showResults: (res: AnalysisResult, id: string) => {
      setResult(res)
      setJobId(id)
      setPhase('results')
    },
    reset: () => {
      if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
      videoRef.current?.pause()
      setPhase('upload')
      setFile(null)
      setInfo(null)
      setResult(null)
      setJobId(null)
      setCurrentFrame(0)
      setError(null)
      setDarkWarning(false)
      onColumnReset()
    },
  }))

  // ── Playback ──────────────────────────────────────────────────────────────

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

  function handleScrub(frame: number) {
    videoRef.current?.pause()
    if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
    setCurrentFrame(frame)
    if (videoRef.current) videoRef.current.currentTime = frame / safeFps
    onPause()
  }

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

        {loading && (
          <div className="card p-4 space-y-4 animate-pulse">
            <div className="h-3 bg-cream/10 rounded w-1/4" />
            <div className="h-2 bg-cream/10 rounded w-full" />
            <div className="h-20 bg-cream/10 rounded w-full" />
          </div>
        )}

        {info && (
          <div className="card p-4 space-y-4">
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
            <span>This video appears dark — pose detection may be less accurate.</span>
          </div>
        )}

        {error && <p className="text-red-400 text-xs text-center">{error}</p>}
      </div>
    )
  }

  // ── Results phase ─────────────────────────────────────────────────────────

  const { label: grade, color: gradeColor } = gradeLabel(result!.efficiency)
  const videoUrl = getVideoUrl(jobId!)

  return (
    <div className="space-y-4">

      <div className="flex items-baseline gap-3">
        <span className="font-display tracking-widest uppercase text-cream/40 text-xs flex-shrink-0">
          {label}
        </span>
        <span className="text-cream font-body text-sm font-medium truncate">{file?.name}</span>
      </div>

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
      </div>

      <div className="card overflow-hidden aspect-video">
        <video
          ref={videoRef}
          src={`${videoUrl}#t=0.001`}
          className="w-full h-full object-contain bg-black"
          preload="auto"
          playsInline
          muted
        />
      </div>

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

      {/* Per-frame metrics */}
      {currentEntry && (
        <div className="card p-3 grid grid-cols-3 divide-x divide-navy-lighter text-center">
          <div className="px-2">
            <div className="text-cream/40 text-xs tracking-widest uppercase mb-1">L Arm</div>
            <div className={`font-display text-xl ${angleColor(currentEntry[5])}`}>
              {currentEntry[5] != null ? `${Math.round(currentEntry[5])}°` : '—'}
            </div>
          </div>
          <div className="px-2">
            <div className="text-cream/40 text-xs tracking-widest uppercase mb-1">R Arm</div>
            <div className={`font-display text-xl ${angleColor(currentEntry[4])}`}>
              {currentEntry[4] != null ? `${Math.round(currentEntry[4])}°` : '—'}
            </div>
          </div>
          <div className="px-2">
            <div className="text-cream/40 text-xs tracking-widest uppercase mb-1">Hips</div>
            <div className={`font-display text-xl ${hipColor(currentEntry[6])}`}>
              {currentEntry[6] != null ? currentEntry[6].toFixed(2) : '—'}
            </div>
          </div>
        </div>
      )}

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
