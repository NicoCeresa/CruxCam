import { useMemo } from 'react'
import Plot from 'react-plotly.js'
import type { PoseEntry } from '../types'

// MediaPipe body connections (landmark indices)
const CONNECTIONS: [number, number][] = [
  [11, 12], // shoulders
  [11, 13], [13, 15], // left arm
  [12, 14], [14, 16], // right arm
  [11, 23], [12, 24], // torso sides
  [23, 24], // hips
  [23, 25], [25, 27], // left upper/lower leg
  [24, 26], [26, 28], // right upper/lower leg
  [27, 29], [29, 31], // left ankle/foot
  [28, 30], [30, 32], // right ankle/foot
  [0, 11],  [0, 12],  // head → shoulders
]

interface AxisRange { x: [number, number]; y: [number, number]; z: [number, number] }

function computeAxisRanges(poseData: PoseEntry[]): AxisRange {
  let minX = Infinity, maxX = -Infinity
  let minY = Infinity, maxY = -Infinity
  let minZ = Infinity, maxZ = -Infinity

  for (const [, lms] of poseData) {
    if (!lms) continue
    for (const [x, y, z] of lms) {
      if (x < minX) minX = x; if (x > maxX) maxX = x
      if (y < minY) minY = y; if (y > maxY) maxY = y
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z
    }
  }

  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  const cz = (minZ + maxZ) / 2
  const half = Math.max(maxX - minX, maxY - minY, maxZ - minZ) / 2 + 0.15

  return {
    x: [cx - half, cx + half],
    y: [cy - half, cy + half],
    z: [cz - half, cz + half],
  }
}

interface Props {
  poseData: PoseEntry[]
  currentFrame: number
  isGood: boolean
}

export default function Skeleton3D({ poseData, currentFrame, isGood }: Props) {
  const axisRanges = useMemo(() => computeAxisRanges(poseData), [poseData])

  // Find nearest entry to currentFrame
  const entry = useMemo(() => {
    if (!poseData.length) return null
    let closest = poseData[0]
    let minDist = Math.abs(poseData[0][0] - currentFrame)
    for (const e of poseData) {
      const d = Math.abs(e[0] - currentFrame)
      if (d < minDist) { minDist = d; closest = e }
    }
    return closest
  }, [poseData, currentFrame])

  const lms = entry?.[1]
  const com = entry?.[3]

  const jointColor   = isGood ? '#7AFF50' : '#FF3232'
  const boneColor    = isGood ? 'rgba(122,255,80,0.5)' : 'rgba(255,50,50,0.5)'

  const traces: Plotly.Data[] = []

  if (lms) {
    // Bones (lines)
    for (const [a, b] of CONNECTIONS) {
      const pa = lms[a], pb = lms[b]
      if (!pa || !pb) continue
      traces.push({
        type: 'scatter3d',
        x: [pa[0], pb[0]],
        y: [pa[2], pb[2]], // swap y/z so y-axis is depth, z is up
        z: [-pa[1], -pb[1]],
        mode: 'lines',
        line: { color: boneColor, width: 4 },
        hoverinfo: 'none',
        showlegend: false,
      })
    }

    // Joints (dots)
    traces.push({
      type: 'scatter3d',
      x: lms.map(p => p[0]),
      y: lms.map(p => p[2]),
      z: lms.map(p => -p[1]),
      mode: 'markers',
      marker: { color: jointColor, size: 4 },
      hoverinfo: 'none',
      showlegend: false,
    })
  }

  // CoM dot
  if (com) {
    traces.push({
      type: 'scatter3d',
      x: [com[0]],
      y: [com[2]],
      z: [-com[1]],
      mode: 'markers',
      marker: { color: '#7FC4FF', size: 8, symbol: 'circle' },
      name: 'CoM',
      hovertemplate: 'CoM<extra></extra>',
    })
  }

  const axisStyle = {
    backgroundcolor: '#1B2D4F',
    gridcolor: '#253D62',
    zerolinecolor: '#253D62',
    color: '#A89E90',
    tickfont: { size: 9, color: '#A89E90' },
    showticklabels: false,
  }

  return (
    <Plot
      data={traces}
      layout={{
        paper_bgcolor: '#0F1E35',
        plot_bgcolor: '#0F1E35',
        margin: { l: 0, r: 0, t: 0, b: 0 },
        scene: {
          bgcolor: '#0F1E35',
          aspectmode: 'cube',
          xaxis: { ...axisStyle, range: axisRanges.x },
          yaxis: { ...axisStyle, range: axisRanges.z },
          zaxis: { ...axisStyle, range: [-axisRanges.y[1], -axisRanges.y[0]] },
          camera: { eye: { x: 1.5, y: 1.5, z: 0.8 } },
        },
        showlegend: false,
      } as Partial<Plotly.Layout>}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height: '100%' }}
      useResizeHandler
    />
  )
}
