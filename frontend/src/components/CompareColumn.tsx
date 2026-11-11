import { forwardRef, lazy, Suspense, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { getVideoInfo, getVideoUrl } from '../api'
import TrimControls from './TrimControls'
import StatTile from './StatTile'
import Alert from './Alert'
import { isToooDark } from '../utils/checkBrightness'
import { angleStatus, gradeLabel, hipStatus, STATUS_TEXT } from '../utils/metrics'
import type { AnalysisResult, PoseEntry, VideoInfo } from '../types'

const Skeleton3D = lazy(() => import('./Skeleton3D'))

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
        <div className="label">{label}</div>

        <div
          className={`card border-dashed border-cream/25 p-6 text-center cursor-pointer transition-colors duration-150
            ${dragging ? 'border-terracotta bg-terracotta/5' : 'hover:border-cream/40'}`}
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
          <Upload size={32} className="mx-auto mb-3 text-muted" aria-hidden />
          {file ? (
            <div className="space-y-1">
              <p className="text-cream font-body font-medium text-sm truncate">{file.name}</p>
              {info && (
                <p className="text-muted text-xs">
                  {info.total_frames} frames · {info.fps} fps
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-cream font-body text-sm">Drop footage here or click to browse</p>
              <p className="text-muted text-xs">MP4, MOV, AVI or MKV</p>
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
          <Alert>This video appears dark — pose detection may be less accurate.</Alert>
        )}

        {error && <p className="text-danger text-sm text-center">{error}</p>}
      </div>
    )
  }

  // ── Results phase ─────────────────────────────────────────────────────────

  const { label: grade, status: gradeStatus } = gradeLabel(result!.efficiency)
  const gradeColor = STATUS_TEXT[gradeStatus]
  const videoUrl = getVideoUrl(jobId!)

  return (
    <div className="space-y-4">

      <div className="flex items-baseline gap-3">
        <span className="label flex-shrink-0">{label}</span>
        <span className="text-cream font-body text-sm font-medium truncate">{file?.name}</span>
      </div>

      <div className="card p-4 flex items-center gap-4">
        <div>
          <div className="label mb-0.5">Efficiency</div>
          <div className="flex items-baseline gap-2">
            <span className={`font-display text-4xl font-bold tabular-nums ${gradeColor}`}>
              {result!.efficiency.toFixed(1)}%
            </span>
            <span className={`font-body text-sm font-semibold ${gradeColor}`}>
              {grade}
            </span>
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
          <Suspense fallback={<div className="h-full bg-cream/5 animate-pulse" />}>
            <Skeleton3D poseData={poseData} currentFrame={currentFrame} isGood={isGoodFrame} />
          </Suspense>
        ) : (
          <div className="flex items-center justify-center h-full text-muted text-sm">
            No pose data
          </div>
        )}
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
          <span className="text-muted text-xs font-body tabular-nums">
            {fmt(currentFrame)} / {fmt(totalFrames)}
          </span>
          <span className="text-xs font-body flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${isGoodFrame ? 'bg-success' : 'bg-danger'}`} />
            <span className="text-muted">{isGoodFrame ? 'Arms open' : 'Compressed'}</span>
          </span>
        </div>
      </div>

    </div>
  )
})

export default CompareColumn
