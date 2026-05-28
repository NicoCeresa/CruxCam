import { useCallback, useEffect, useRef, useState } from 'react'
import CompareColumn, { type CompareColumnHandle } from '../components/CompareColumn'
import { submitPreview, getResult, getStreamUrl } from '../api'
import type { JobStatus } from '../types'

type PagePhase = 'setup' | 'analyzing' | 'done'

interface JobState {
  jobId: string | null
  progress: number
  done: boolean
  error: string | null
}

const INIT_JOB: JobState = { jobId: null, progress: 0, done: false, error: null }

function JobProgressBar({ job, label }: { job: JobState; label: string }) {
  if (!job.jobId && !job.error) return null
  const isActive = job.jobId !== null && !job.done && !job.error
  const indeterminate = isActive && job.progress === 0
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-cream/60 font-body tracking-wider uppercase">{label}</span>
        {job.error ? (
          <span className="text-red-400 font-body">{job.error}</span>
        ) : job.progress >= 1 && !job.done ? (
          <span className="text-cream/40">Finalizing…</span>
        ) : indeterminate ? (
          <span className="text-cream/40">Processing…</span>
        ) : (
          <span className="text-cream/40 tabular-nums">{Math.round(job.progress * 100)}%</span>
        )}
      </div>
      <div className="h-1.5 bg-navy-lighter rounded-full overflow-hidden relative">
        {indeterminate ? (
          <div className="absolute h-full w-1/3 rounded-full bg-terracotta animate-bar-slide" />
        ) : (
          <div
            className={`h-full rounded-full transition-all duration-300 ${job.error ? 'bg-red-400' : 'bg-terracotta'}`}
            style={{ width: `${Math.round(job.progress * 100)}%` }}
          />
        )}
      </div>
    </div>
  )
}

export default function ComparePage() {
  const [pagePhase, setPagePhase] = useState<PagePhase>('setup')
  const [isPlaying, setIsPlaying] = useState(false)
  const [aReady, setAReady] = useState(false)
  const [bReady, setBReady] = useState(false)
  const [jobA, setJobA] = useState<JobState>(INIT_JOB)
  const [jobB, setJobB] = useState<JobState>(INIT_JOB)

  const aRef = useRef<CompareColumnHandle>(null)
  const bRef = useRef<CompareColumnHandle>(null)
  // Prevents duplicate getResult calls if SSE fires complete more than once
  const fetchingRef = useRef(new Set<string>())

  const pause = useCallback(() => setIsPlaying(false), [])

  async function handleAnalyze() {
    const argsA = aRef.current?.getUploadArgs() ?? null
    const argsB = bRef.current?.getUploadArgs() ?? null
    if (!argsA && !argsB) return

    setPagePhase('analyzing')
    setJobA(INIT_JOB)
    setJobB(INIT_JOB)

    const [resA, resB] = await Promise.allSettled([
      argsA
        ? submitPreview(argsA.info.preview_id, argsA.angleThreshold, argsA.trimStart, argsA.trimEnd)
        : Promise.resolve<string | null>(null),
      argsB
        ? submitPreview(argsB.info.preview_id, argsB.angleThreshold, argsB.trimStart, argsB.trimEnd)
        : Promise.resolve<string | null>(null),
    ])

    const newA: JobState =
      resA.status === 'fulfilled' && resA.value !== null
        ? { jobId: resA.value, progress: 0, done: false, error: null }
        : { jobId: null, progress: 0, done: true, error: resA.status === 'rejected' ? String((resA as PromiseRejectedResult).reason) : null }

    const newB: JobState =
      resB.status === 'fulfilled' && resB.value !== null
        ? { jobId: resB.value, progress: 0, done: false, error: null }
        : { jobId: null, progress: 0, done: true, error: resB.status === 'rejected' ? String((resB as PromiseRejectedResult).reason) : null }

    setJobA(newA)
    setJobB(newB)
  }

  // SSE for job A
  useEffect(() => {
    const jid = jobA.jobId
    if (!jid || jobA.done) return
    const es = new EventSource(getStreamUrl(jid))
    es.onmessage = (e) => {
      const status: JobStatus = JSON.parse(e.data)
      if (status.status === 'complete') {
        es.close()
        if (!fetchingRef.current.has(jid)) {
          fetchingRef.current.add(jid)
          setJobA(j => ({ ...j, progress: 1 }))
          getResult(jid)
            .then(result => { aRef.current?.showResults(result, jid); setJobA(j => ({ ...j, done: true })) })
            .catch(err => setJobA(j => ({ ...j, error: err instanceof Error ? err.message : 'Failed to load results', done: true })))
            .finally(() => fetchingRef.current.delete(jid))
        }
      } else if (status.status === 'failed') {
        es.close()
        setJobA(j => ({ ...j, error: status.error ?? 'Processing failed', done: true }))
      } else {
        setJobA(j => ({ ...j, progress: status.progress ?? 0 }))
      }
    }
    es.onerror = () => setJobA(j => ({ ...j, error: 'Connection lost', done: true }))
    return () => es.close()
  }, [jobA.jobId, jobA.done])

  // SSE for job B
  useEffect(() => {
    const jid = jobB.jobId
    if (!jid || jobB.done) return
    const es = new EventSource(getStreamUrl(jid))
    es.onmessage = (e) => {
      const status: JobStatus = JSON.parse(e.data)
      if (status.status === 'complete') {
        es.close()
        if (!fetchingRef.current.has(jid)) {
          fetchingRef.current.add(jid)
          setJobB(j => ({ ...j, progress: 1 }))
          getResult(jid)
            .then(result => { bRef.current?.showResults(result, jid); setJobB(j => ({ ...j, done: true })) })
            .catch(err => setJobB(j => ({ ...j, error: err instanceof Error ? err.message : 'Failed to load results', done: true })))
            .finally(() => fetchingRef.current.delete(jid))
        }
      } else if (status.status === 'failed') {
        es.close()
        setJobB(j => ({ ...j, error: status.error ?? 'Processing failed', done: true }))
      } else {
        setJobB(j => ({ ...j, progress: status.progress ?? 0 }))
      }
    }
    es.onerror = () => setJobB(j => ({ ...j, error: 'Connection lost', done: true }))
    return () => es.close()
  }, [jobB.jobId, jobB.done])

  // Transition to done once all submitted jobs finish successfully.
  // Guard 1: don't fire before uploads resolve (jobIds still null = still in-flight).
  // Guard 2: if every submitted job failed, stay in 'analyzing' so error bars are visible.
  useEffect(() => {
    if (pagePhase !== 'analyzing') return
    const anyDispatched =
      jobA.jobId !== null || jobB.jobId !== null ||
      jobA.error !== null || jobB.error !== null
    if (!anyDispatched) return
    const aDone = !jobA.jobId || jobA.done
    const bDone = !jobB.jobId || jobB.done
    if (!aDone || !bDone) return
    const anySuccess = (jobA.jobId !== null && !jobA.error) || (jobB.jobId !== null && !jobB.error)
    if (anySuccess) setPagePhase('done')
    // All failed → stay in 'analyzing' so error bars remain visible
  }, [pagePhase, jobA, jobB])

  function handleReset() {
    setPagePhase('setup')
    setIsPlaying(false)
    setJobA(INIT_JOB)
    setJobB(INIT_JOB)
    setAReady(false)
    setBReady(false)
    aRef.current?.reset()
    bRef.current?.reset()
  }

  const canAnalyze = pagePhase === 'setup' && (aReady || bReady)

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="font-display text-4xl tracking-widest uppercase text-cream">Compare</h1>
        <p className="text-cream/50 text-sm font-body">
          Analyze two clips side by side to compare technique and efficiency.
        </p>
      </div>

      {/* Processing panel */}
      {pagePhase === 'analyzing' && (() => {
        const allFailed =
          (jobA.error !== null || jobB.error !== null) &&
          (!jobA.jobId || jobA.done) && (!jobB.jobId || jobB.done) &&
          !((jobA.jobId !== null && !jobA.error) || (jobB.jobId !== null && !jobB.error))
        const allFinalizing =
          !allFailed &&
          (!jobA.jobId || jobA.progress >= 1) &&
          (!jobB.jobId || jobB.progress >= 1)
        return (
          <div className="card p-8 space-y-6 max-w-md mx-auto">
            <div className="text-center space-y-2">
              <div className="font-display text-2xl tracking-widest uppercase text-cream">
                {allFailed ? 'Upload Failed' : 'Analyzing Footage'}
              </div>
              <p className="text-cream/40 text-sm font-body">
                {allFailed
                  ? 'Could not start processing — re-drop your videos and try again.'
                  : allFinalizing
                  ? 'Downloading results…'
                  : 'Processing both videos in parallel…'}
              </p>
            </div>
            <div className="space-y-5">
              <JobProgressBar job={jobA} label="Video A" />
              <JobProgressBar job={jobB} label="Video B" />
            </div>
            {allFailed && (
              <button className="btn-ghost w-full" onClick={handleReset}>
                Try Again
              </button>
            )}
          </div>
        )
      })()}

      {/* Columns — always mounted; hidden while analyzing to preserve component state */}
      <div className={`grid grid-cols-1 md:grid-cols-2 gap-8 ${pagePhase === 'analyzing' ? 'hidden' : ''}`}>
        <CompareColumn
          ref={aRef}
          label="Video A"
          sharedPlaying={isPlaying}
          onPause={pause}
          onColumnReset={() => setIsPlaying(false)}
          onReadyChange={setAReady}
        />
        <CompareColumn
          ref={bRef}
          label="Video B"
          sharedPlaying={isPlaying}
          onPause={pause}
          onColumnReset={() => setIsPlaying(false)}
          onReadyChange={setBReady}
        />
      </div>

      {/* Shared controls */}
      <div className="flex justify-center gap-4 pt-2">
        {canAnalyze && (
          <button className="btn-primary px-10 py-3" onClick={handleAnalyze}>
            Analyze Footage
          </button>
        )}
        {pagePhase === 'done' && (
          <>
            <button className="btn-primary px-10 py-3" onClick={() => setIsPlaying(p => !p)}>
              {isPlaying ? '⏸ Pause' : '▶ Play'}
            </button>
            <button className="btn-ghost px-8 py-3" onClick={handleReset}>
              Analyze New Videos
            </button>
          </>
        )}
      </div>
    </div>
  )
}
