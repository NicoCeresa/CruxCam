import { useCallback, useEffect, useRef, useState } from 'react'
import CompareColumn, { type CompareColumnHandle } from '../components/CompareColumn'
import { submitPreview, getStatus, getResult } from '../api'

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
      <div className="h-1.5 bg-navy-lighter rounded-full overflow-hidden">
        {indeterminate ? (
          <div className="h-full w-1/3 rounded-full bg-terracotta animate-pulse" />
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
  // Refs mirror state so polling closure always sees current values
  const jobARef = useRef<JobState>(INIT_JOB)
  const jobBRef = useRef<JobState>(INIT_JOB)

  useEffect(() => { jobARef.current = jobA }, [jobA])
  useEffect(() => { jobBRef.current = jobB }, [jobB])

  const pause = useCallback(() => setIsPlaying(false), [])

  async function handleAnalyze() {
    const argsA = aRef.current?.getUploadArgs() ?? null
    const argsB = bRef.current?.getUploadArgs() ?? null
    if (!argsA && !argsB) return

    setPagePhase('analyzing')
    // Reset job state and sync refs immediately so polling starts fresh
    const resetA = INIT_JOB
    const resetB = INIT_JOB
    setJobA(resetA); jobARef.current = resetA
    setJobB(resetB); jobBRef.current = resetB

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

    setJobA(newA); jobARef.current = newA
    setJobB(newB); jobBRef.current = newB
  }

  // Polling — active only while analyzing
  useEffect(() => {
    if (pagePhase !== 'analyzing') return

    const tick = () => {
      const a = jobARef.current
      const b = jobBRef.current
      const polls: Promise<void>[] = []

      if (a.jobId && !a.done) {
        polls.push(
          getStatus(a.jobId)
            .then(async status => {
              if (status.status === 'complete') {
                setJobA(j => ({ ...j, progress: 1 }))
                const result = await getResult(a.jobId!)
                aRef.current?.showResults(result, a.jobId!)
                setJobA(j => ({ ...j, done: true }))
              } else if (status.status === 'failed') {
                setJobA(j => ({ ...j, error: status.error ?? 'Processing failed', done: true }))
              } else {
                setJobA(j => ({ ...j, progress: status.progress ?? 0 }))
              }
            })
            .catch(e => {
              setJobA(j => ({ ...j, error: e instanceof Error ? e.message : 'Polling failed', done: true }))
            })
        )
      }

      if (b.jobId && !b.done) {
        polls.push(
          getStatus(b.jobId)
            .then(async status => {
              if (status.status === 'complete') {
                setJobB(j => ({ ...j, progress: 1 }))
                const result = await getResult(b.jobId!)
                bRef.current?.showResults(result, b.jobId!)
                setJobB(j => ({ ...j, done: true }))
              } else if (status.status === 'failed') {
                setJobB(j => ({ ...j, error: status.error ?? 'Processing failed', done: true }))
              } else {
                setJobB(j => ({ ...j, progress: status.progress ?? 0 }))
              }
            })
            .catch(e => {
              setJobB(j => ({ ...j, error: e instanceof Error ? e.message : 'Polling failed', done: true }))
            })
        )
      }

      void Promise.allSettled(polls)
    }

    const id = setInterval(tick, 1500)
    tick()
    return () => clearInterval(id)
  }, [pagePhase])

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
