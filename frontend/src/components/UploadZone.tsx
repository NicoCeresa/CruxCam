import { useCallback, useRef, useState } from 'react'
import { getSampleInfo, getVideoInfo, submitPreview, uploadSample } from '../api'
import TrimControls from './TrimControls'
import { isToooDark } from '../utils/checkBrightness'
import type { VideoInfo } from '../types'

interface Props {
  onJobStart: (jobId: string, info: VideoInfo) => void
}

const ACCEPT = '.mp4,.mov,.avi,.mkv,video/*'

export default function UploadZone({ onJobStart }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [useSample, setUseSample] = useState(false)
  const [info, setInfo] = useState<VideoInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  const [angleThreshold, setAngleThreshold] = useState(90)
  const [trimStart, setTrimStart] = useState(0)
  const [trimEnd, setTrimEnd] = useState(0)
  const [darkWarning, setDarkWarning] = useState(false)

  const inputRef = useRef<HTMLInputElement>(null)

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

  async function handleToggleSample(checked: boolean) {
    setUseSample(checked)
    setFile(null)
    setInfo(null)
    setError(null)
    if (checked) {
      setLoading(true)
      try {
        const i = await getSampleInfo()
        setInfo(i)
        setTrimStart(0)
        setTrimEnd(i.total_frames - 1)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Could not load sample')
        setUseSample(false)
      } finally {
        setLoading(false)
      }
    }
  }

  async function handleSubmit() {
    if (!info) return
    setError(null)
    setLoading(true)
    try {
      const jobId = useSample
        ? await uploadSample(info.preview_id, angleThreshold, trimStart, trimEnd)
        : await submitPreview(info.preview_id, angleThreshold, trimStart, trimEnd)
      onJobStart(jobId, info)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Hero */}
      <div className="text-center space-y-2">
        <h1 className="font-display text-4xl font-700 tracking-widest uppercase text-cream">
          Analyze Your Send
        </h1>
        <p className="text-cream/50 text-sm tracking-wide">
          Upload climbing footage and learn how your body moves throughout the climb.
        </p>
      </div>

      {/* Sample video toggle */}
      <label className="flex items-center gap-3 cursor-pointer select-none w-fit">
        <input
          type="checkbox"
          checked={useSample}
          onChange={e => handleToggleSample(e.target.checked)}
          className="w-4 h-4 accent-terracotta"
        />
        <span className="text-cream/60 text-sm font-body">Use sample video</span>
        {useSample && info && (
          <span className="text-cream/30 text-xs">
            {info.total_frames} frames · {info.fps} fps
          </span>
        )}
      </label>

      {/* Drop zone — hidden when sample is active */}
      {!useSample && (
        <div
          className={`card p-10 text-center cursor-pointer transition-colors duration-150
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

          {/* Mountain silhouette */}
          <svg viewBox="0 0 120 70" className="w-20 h-12 mx-auto mb-4 text-cream/20">
            <path d="M5,70 L45,8 L65,35 L85,5 L115,70 Z" fill="currentColor" />
          </svg>

          {file ? (
            <div className="space-y-1">
              <p className="text-cream font-body font-medium">{file.name}</p>
              {info && (
                <p className="text-cream/40 text-xs">
                  {info.total_frames} frames · {info.fps} fps · {info.width}×{info.height}
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-cream/70 font-body">Drop footage here or click to browse</p>
              <p className="text-cream/30 text-xs tracking-wider uppercase">MP4 · MOV · AVI · MKV</p>
            </div>
          )}
        </div>
      )}

      {/* Loading skeleton while video info is being read */}
      {loading && !info && (
        <div className="card p-6 space-y-6 animate-pulse">
          <div className="h-3 bg-cream/10 rounded w-1/4" />
          <div className="h-2 bg-cream/10 rounded w-full" />
          <div className="border-t border-navy-lighter" />
          <div className="h-24 bg-cream/10 rounded w-full" />
        </div>
      )}

      {/* Controls — only shown after info loads */}
      {info && (
        <div className="card p-6 space-y-6">
          {/* Angle threshold */}
          <div className="flex items-center justify-between gap-6">
            <div>
              <label className="block text-xs tracking-wider uppercase text-cream/50 mb-1">
                Arm Angle Threshold
              </label>
              <p className="text-cream/30 text-xs">
                Frames where both elbows are below this angle count as "compressed"
              </p>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <input
                type="range"
                min={30} max={120} step={5}
                value={angleThreshold}
                onChange={e => setAngleThreshold(Number(e.target.value))}
                className="w-28 accent-terracotta"
              />
              <span className="font-display text-2xl text-terracotta w-12 text-right">
                {angleThreshold}°
              </span>
            </div>
          </div>

          <div className="border-t border-navy-lighter" />

          {/* Trim */}
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

      {/* Brightness warning */}
      {darkWarning && (
        <div className="border border-yellow-500/40 bg-yellow-500/10 px-4 py-3 text-yellow-400 text-xs font-body flex items-start gap-2">
          <span className="flex-shrink-0">⚠</span>
          <span>This video appears dark — pose detection may be less accurate. Improving lighting before recording will give better results.</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="text-red-400 text-sm text-center">{error}</p>
      )}

      {/* Submit */}
      <button
        className="btn-primary w-full"
        onClick={handleSubmit}
        disabled={(!file && !useSample) || !info || loading}
      >
        {loading ? 'Loading…' : 'Analyze Footage'}
      </button>
    </div>
  )
}
