import { lazy, Suspense, useState } from 'react'
import Header from './components/Header'
import UploadZone from './components/UploadZone'
import ProcessingView from './components/ProcessingView'
import type { AnalysisResult, VideoInfo } from './types'

const ResultsPanel = lazy(() => import('./components/ResultsPanel'))

type Phase = 'upload' | 'processing' | 'results'

export default function App() {
  const [phase, setPhase] = useState<Phase>('upload')
  const [jobId, setJobId] = useState<string | null>(null)
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)

  function handleJobStart(id: string, info: VideoInfo) {
    setJobId(id)
    setVideoInfo(info)
    setPhase('processing')
  }

  function handleComplete(res: AnalysisResult) {
    setResult(res)
    setPhase('results')
  }

  function handleReset() {
    setPhase('upload')
    setJobId(null)
    setVideoInfo(null)
    setResult(null)
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-10">
        {phase === 'upload' && (
          <UploadZone onJobStart={handleJobStart} />
        )}
        {phase === 'processing' && jobId && (
          <ProcessingView jobId={jobId} onComplete={handleComplete} />
        )}
        {phase === 'results' && result && videoInfo && jobId && (
          <Suspense fallback={<div className="text-cream/50 text-center py-20">Loading results…</div>}>
            <ResultsPanel
              result={result}
              videoInfo={videoInfo}
              jobId={jobId}
              onReset={handleReset}
            />
          </Suspense>
        )}
      </main>
    </div>
  )
}
