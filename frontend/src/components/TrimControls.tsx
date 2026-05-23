import { useEffect, useState } from 'react'
import { getPreviewFrameUrl } from '../api'

interface Props {
  previewId: string
  totalFrames: number
  fps: number
  start: number
  end: number
  onChange: (start: number, end: number) => void
}

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}

function FrameThumb({ src, label }: { src: string; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <img
        src={src}
        alt=""
        className="w-full aspect-video object-cover border border-navy-lighter"
      />
      <span className="text-xs text-cream/30 font-body">{label}</span>
    </div>
  )
}

export default function TrimControls({ previewId, totalFrames, fps, start, end, onChange }: Props) {
  const max = totalFrames - 1
  const debouncedStart = useDebounce(start, 150)
  const debouncedEnd = useDebounce(end, 150)

  const startThumbUrl = getPreviewFrameUrl(previewId, debouncedStart)
  const endThumbUrl   = getPreviewFrameUrl(previewId, debouncedEnd)

  const startPct = (start / max) * 100
  const endPct   = (end / max) * 100

  // Keep start from overtaking end and vice versa
  function handleStart(e: React.ChangeEvent<HTMLInputElement>) {
    const v = Math.min(Number(e.target.value), end - 1)
    onChange(v, end)
  }
  function handleEnd(e: React.ChangeEvent<HTMLInputElement>) {
    const v = Math.max(Number(e.target.value), start + 1)
    onChange(start, v)
  }

  function fmt(frames: number) {
    const secs = frames / Math.max(fps, 1)
    const m = Math.floor(secs / 60).toString().padStart(2, '0')
    const s = Math.floor(secs % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-cream/50 font-body">
        <span>Trim</span>
        <span>{fmt(start)} – {fmt(end)}</span>
      </div>

      {/* Dual-handle slider */}
      <div className="range-track">
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 bg-navy-lighter rounded-full" />
        <div
          className="absolute top-1/2 -translate-y-1/2 h-1.5 bg-terracotta rounded-full"
          style={{ left: `${startPct}%`, right: `${100 - endPct}%` }}
        />
        <input
          type="range"
          className="range-thumb"
          min={0} max={max}
          value={start}
          onChange={handleStart}
        />
        <input
          type="range"
          className="range-thumb"
          min={0} max={max}
          value={end}
          onChange={handleEnd}
        />
      </div>

      {/* Thumbnails below slider */}
      <div className="grid grid-cols-2 gap-3">
        <FrameThumb src={startThumbUrl} label={`Start · ${fmt(start)}`} />
        <FrameThumb src={endThumbUrl}   label={`End · ${fmt(end)}`} />
      </div>
    </div>
  )
}
