import { useCallback, useRef, useState } from 'react'
import CompareColumn, { type CompareColumnHandle } from '../components/CompareColumn'

export default function ComparePage() {
  const [isPlaying, setIsPlaying] = useState(false)
  const [aReady, setAReady]       = useState(false)
  const [bReady, setBReady]       = useState(false)
  const [aCanSubmit, setACanSubmit] = useState(false)
  const [bCanSubmit, setBCanSubmit] = useState(false)

  const aRef = useRef<CompareColumnHandle>(null)
  const bRef = useRef<CompareColumnHandle>(null)

  const hasAnyResults  = aReady || bReady
  const canAnalyze     = aCanSubmit || bCanSubmit

  const pause        = useCallback(() => setIsPlaying(false), [])
  const resetA       = useCallback(() => { setAReady(false); setIsPlaying(false) }, [])
  const resetB       = useCallback(() => { setBReady(false); setIsPlaying(false) }, [])
  const markAReady   = useCallback(() => setAReady(true), [])
  const markBReady   = useCallback(() => setBReady(true), [])

  function handleAnalyze() {
    aRef.current?.submit()
    bRef.current?.submit()
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="font-display text-4xl tracking-widest uppercase text-cream">Compare</h1>
        <p className="text-cream/50 text-sm font-body">
          Analyze two clips side by side to compare technique and efficiency.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <CompareColumn
          ref={aRef}
          label="Video A"
          sharedPlaying={isPlaying}
          onPause={pause}
          onResultsReady={markAReady}
          onColumnReset={resetA}
          onReadyChange={setACanSubmit}
        />
        <CompareColumn
          ref={bRef}
          label="Video B"
          sharedPlaying={isPlaying}
          onPause={pause}
          onResultsReady={markBReady}
          onColumnReset={resetB}
          onReadyChange={setBCanSubmit}
        />
      </div>

      {/* Shared controls */}
      <div className="flex justify-center gap-4 pt-2">
        {canAnalyze && (
          <button className="btn-primary px-10 py-3" onClick={handleAnalyze}>
            Analyze Footage
          </button>
        )}
        {hasAnyResults && (
          <button className="btn-primary px-10 py-3" onClick={() => setIsPlaying(p => !p)}>
            {isPlaying ? '⏸ Pause' : '▶ Play'}
          </button>
        )}
      </div>
    </div>
  )
}
