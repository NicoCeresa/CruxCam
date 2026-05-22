import { lazy, Suspense, useState } from 'react'
import { BrowserRouter, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import Header from './components/Header'
import UploadZone from './components/UploadZone'
import ProcessingView from './components/ProcessingView'
import type { AnalysisResult, VideoInfo } from './types'

const ResultsPanel = lazy(() => import('./components/ResultsPanel'))

function UploadPage() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<'upload' | 'processing'>('upload')
  const [jobId, setJobId] = useState<string | null>(null)
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null)

  function handleJobStart(id: string, info: VideoInfo) {
    setJobId(id)
    setVideoInfo(info)
    setPhase('processing')
  }

  function handleComplete(res: AnalysisResult) {
    navigate(`/results/${jobId}`, { state: { result: res, videoInfo } })
  }

  return (
    <>
      {phase === 'upload' && <UploadZone onJobStart={handleJobStart} />}
      {phase === 'processing' && jobId && (
        <ProcessingView jobId={jobId} onComplete={handleComplete} />
      )}
    </>
  )
}

function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { state } = useLocation()
  const navigate = useNavigate()

  const result   = state?.result   as AnalysisResult | undefined
  const videoInfo = state?.videoInfo as VideoInfo | undefined

  if (!result || !videoInfo || !jobId) {
    navigate('/')
    return null
  }

  return (
    <Suspense fallback={<div className="text-cream/50 text-center py-20">Loading results…</div>}>
      <ResultsPanel
        result={result}
        videoInfo={videoInfo}
        jobId={jobId}
        onReset={() => navigate('/')}
      />
    </Suspense>
  )
}

function AppContent() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen flex flex-col">
      <Header onHome={() => navigate('/')} />
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-10">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/results/:jobId" element={<ResultsPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}
