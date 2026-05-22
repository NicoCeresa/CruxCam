import type { AnalysisResult, JobStatus, VideoInfo } from './types'

// In dev, Vite proxies /api → localhost:8000 (see vite.config.ts).
// In production, set VITE_API_URL to the deployed FastAPI base URL.
const BASE = import.meta.env.VITE_API_URL ?? '/api'

async function checkOk(res: Response): Promise<Response> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    try {
      const json = JSON.parse(text)
      throw new Error(json.detail ?? text)
    } catch {
      throw new Error(text)
    }
  }
  return res
}

export async function getSampleInfo(): Promise<VideoInfo> {
  const res = await checkOk(await fetch(`${BASE}/sample/info`))
  return res.json()
}

export async function uploadSample(
  previewId: string,
  angleThreshold: number,
  startFrame: number,
  endFrame: number,
): Promise<string> {
  const params = new URLSearchParams({
    angle_threshold: String(angleThreshold),
    start_frame: String(startFrame),
    end_frame: String(endFrame),
    preview_id: previewId,
  })
  const res = await checkOk(
    await fetch(`${BASE}/sample/upload?${params}`, { method: 'POST' }),
  )
  const { job_id } = await res.json()
  return job_id as string
}

export async function getVideoInfo(file: File): Promise<VideoInfo> {
  const form = new FormData()
  form.append('video', file)
  const res = await checkOk(await fetch(`${BASE}/info`, { method: 'POST', body: form }))
  return res.json()
}

export function getPreviewFrameUrl(previewId: string, n: number): string {
  return `${BASE}/frame/${previewId}?n=${n}`
}

export async function uploadVideo(
  file: File,
  previewId: string,
  angleThreshold: number,
  startFrame: number,
  endFrame: number,
): Promise<string> {
  const form = new FormData()
  form.append('video', file)
  const params = new URLSearchParams({
    angle_threshold: String(angleThreshold),
    start_frame: String(startFrame),
    end_frame: String(endFrame),
    preview_id: previewId,
  })
  const res = await checkOk(
    await fetch(`${BASE}/upload?${params}`, { method: 'POST', body: form }),
  )
  const { job_id } = await res.json()
  return job_id as string
}

export async function getStatus(jobId: string): Promise<JobStatus> {
  const res = await checkOk(await fetch(`${BASE}/status/${jobId}`))
  return res.json()
}

export async function getResult(jobId: string): Promise<AnalysisResult> {
  const res = await checkOk(await fetch(`${BASE}/result/${jobId}`))
  return res.json()
}

export function getVideoUrl(jobId: string): string {
  return `${BASE}/video/${jobId}`
}

export function getSkeletonVideoUrl(jobId: string): string {
  return `${BASE}/skeleton_video/${jobId}`
}
