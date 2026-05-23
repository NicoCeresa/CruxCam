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

function FrameThumb({ src }: { src: string }) {
  return (
    <img
      src={src}
      alt=""
      className="w-28 h-20 object-cover border border-navy-lighter flex-shrink-0"
    />
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
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-cream/50 font-body">
        <span>Trim</span>
        <span>{fmt(start)} – {fmt(end)}</span>
      </div>

      <div className="flex items-center gap-3">
        <FrameThumb src={startThumbUrl} />

        {/* Dual-handle slider */}
        <div className="range-track flex-1">
          {/* Background track */}
          <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 bg-navy-lighter rounded-full" />
          {/* Selected range fill */}
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

        <FrameThumb src={endThumbUrl} />
      </div>

      <div className="flex justify-between text-xs text-cream/30 font-body px-[76px]">
        <span>Frame {start}</span>
        <span>Frame {end}</span>
      </div>
    </div>
  )
}
