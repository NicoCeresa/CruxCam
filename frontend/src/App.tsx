import { lazy, Suspense, useState } from 'react'
import { BrowserRouter, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import Header from './components/Header'
import UploadZone from './components/UploadZone'
import ProcessingView from './components/ProcessingView'
import HomePage from './pages/HomePage'
import ComparePage from './pages/ComparePage'
import type { AnalysisResult, VideoInfo } from './types'

const ResultsPanel = lazy(() => import('./components/ResultsPanel'))

function AnalyzePage() {
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

  const result    = state?.result    as AnalysisResult | undefined
  const videoInfo = state?.videoInfo as VideoInfo | undefined

  if (!result || !videoInfo || !jobId) {
    navigate('/analyze')
    return null
  }

  return (
    <Suspense fallback={<div className="text-cream/50 text-center py-20">Loading results…</div>}>
      <ResultsPanel
        result={result}
        videoInfo={videoInfo}
        jobId={jobId}
        onReset={() => navigate('/analyze')}
      />
    </Suspense>
  )
}

function AppContent() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-10">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/results/:jobId" element={<ResultsPage />} />
          <Route path="/compare" element={<ComparePage />} />
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
