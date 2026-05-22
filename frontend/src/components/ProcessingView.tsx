import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getResult, getStatus } from '../api'
import type { AnalysisResult } from '../types'

const MESSAGES = [
  'Reading the route…',
  'Analyzing movement…',
  'Mapping your beta…',
  'Calculating efficiency…',
  'Processing footage…',
  'Tracking landmarks…',
]

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

  // Cycle status messages independently of polling
  const msgIdxRef = useRef(0)
  useEffect(() => {
    const id = setInterval(() => {
      msgIdxRef.current = (msgIdxRef.current + 1) % MESSAGES.length
      setStatusText(MESSAGES[msgIdxRef.current])
    }, 2500)
    return () => clearInterval(id)
  }, [])

  // Polling — stable interval, only recreated if jobId changes
  useEffect(() => {
    let stopped = false
    let lastProgress = -1
    let lastProgressAt = Date.now()
    let networkErrors = 0
    const STALL_MS = 60_000

    const id = setInterval(async () => {
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
            clearInterval(id)
            setError('Processing stalled — the worker may have run out of memory. Try a shorter clip.')
            return
          }
          setProgress(status.progress)
          return
        }
        if (status.status === 'complete') {
          stopped = true
          clearInterval(id)
          setProgress(1)
          const result = await getResult(jobId)
          onCompleteRef.current(result)
          return
        }
        if (status.status === 'failed') {
          stopped = true
          clearInterval(id)
          setError(status.error ?? 'Processing failed')
        }
      } catch (e) {
        networkErrors++
        if (networkErrors >= 3) {
          stopped = true
          clearInterval(id)
          setError('Connection lost — check your network and try again.')
        }
      }
    }, 1000)

    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [jobId])

  if (error) {
    return (
      <div className="max-w-md mx-auto text-center space-y-4 py-20">
        <p className="text-red-400 text-sm">{error}</p>
        <button className="btn-ghost" onClick={() => navigate('/')}>
          Try again
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto py-20 space-y-8">
      <div className="text-center space-y-2">
        <h2 className="font-display text-3xl tracking-widest uppercase text-cream">
          On the Wall
        </h2>
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
        <svg viewBox="0 0 60 60" className="w-12 h-12 text-brown-light animate-spin" style={{ animationDuration: '3s' }}>
          <circle cx="30" cy="30" r="20" stroke="currentColor" strokeWidth="3" fill="none" strokeDasharray="30 95" strokeLinecap="round" />
          <circle cx="30" cy="30" r="12" stroke="currentColor" strokeWidth="2" fill="none" strokeDasharray="18 57" strokeLinecap="round" strokeDashoffset="20" />
        </svg>
      </div>
    </div>
  )
}
