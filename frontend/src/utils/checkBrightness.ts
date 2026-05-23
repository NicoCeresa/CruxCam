import { getPreviewFrameUrl } from '../api'

const BRIGHTNESS_THRESHOLD = 0.2

function sampleFrame(previewId: string, frameNum: number): Promise<number> {
  return new Promise(resolve => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = 64
      canvas.height = 36
      const ctx = canvas.getContext('2d')
      if (!ctx) { resolve(1); return }
      ctx.drawImage(img, 0, 0, 64, 36)
      const { data } = ctx.getImageData(0, 0, 64, 36)
      let sum = 0
      for (let i = 0; i < data.length; i += 4) {
        sum += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]
      }
      resolve(sum / (data.length / 4) / 255)
    }
    img.onerror = () => resolve(1) // can't sample — assume fine
    img.src = getPreviewFrameUrl(previewId, frameNum)
  })
}

// Samples frames at 25%, 50%, and 75% through the clip and returns true if too dark.
export async function isToooDark(previewId: string, totalFrames: number): Promise<boolean> {
  const frames = [0.25, 0.5, 0.75].map(p => Math.floor(p * totalFrames))
  const luminances = await Promise.all(frames.map(f => sampleFrame(previewId, f)))
  const avg = luminances.reduce((a, b) => a + b, 0) / luminances.length
  return avg < BRIGHTNESS_THRESHOLD
}
