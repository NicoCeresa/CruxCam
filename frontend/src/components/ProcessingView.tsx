import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoaderCircle } from 'lucide-react'
import { getResult, getStreamUrl } from '../api'
import type { AnalysisResult, JobStatus } from '../types'

interface Props {
  jobId: string
  onComplete: (result: AnalysisResult) => void
}

export default function ProcessingView({ jobId, onComplete }: Props) {
  const navigate = useNavigate()
  const [progress, setProgress]     = useState(0)
  const [statusText, setStatusText] = useState('Waiting for worker…')
  const [error, setError]           = useState<string | null>(null)

  // Keep a stable ref to onComplete so the polling closure never goes stale
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  // SSE — one persistent connection per job replacing the polling interval
  useEffect(() => {
    let lastProgress = -1
    let lastProgressAt = Date.now()
    let networkErrors = 0
    const STALL_MS = 60_000

    const es = new EventSource(getStreamUrl(jobId))

    es.onmessage = (e) => {
      networkErrors = 0
      const status: JobStatus = JSON.parse(e.data)

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
          es.close()
          setError('Processing stalled — the worker may have run out of memory. Try a shorter clip.')
          return
        }
        setStatusText('Analyzing frames…')
        setProgress(status.progress)
        return
      }
      if (status.status === 'complete') {
        es.close()
        setProgress(1)
        setStatusText('Loading results…')
        getResult(jobId).then(result => onCompleteRef.current(result))
        return
      }
      if (status.status === 'failed') {
        es.close()
        setError(status.error ?? 'Processing failed')
      }
    }

    es.onerror = () => {
      networkErrors++
      if (networkErrors >= 3) {
        es.close()
        setError('Connection lost — check your network and try again.')
      }
    }

    return () => es.close()
  }, [jobId])

  if (error) {
    return (
      <div className="max-w-md mx-auto text-center space-y-4 py-20">
        <p className="text-danger text-sm">{error}</p>
        <button className="btn-ghost" onClick={() => navigate('/')}>
          Try again
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto py-20 space-y-8">
      <div className="text-center space-y-3">
        <LoaderCircle size={32} className="mx-auto text-terracotta animate-spin" aria-hidden />
        <h2 className="font-display text-3xl font-bold tracking-wide uppercase text-cream">
          Analyzing your climb
        </h2>
        <p className="text-muted text-sm" aria-live="polite">{statusText}</p>
      </div>

      <div className="space-y-2">
        <div className="efficiency-bar">
          <div
            className="h-full bg-terracotta transition-all duration-200 ease-out"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>
        <div className="text-xs text-muted font-body tabular-nums text-right">
          {Math.round(progress * 100)}%
        </div>
      </div>
    </div>
  )
}
