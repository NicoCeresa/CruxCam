import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { PoseEntry } from '../types'

const CONNECTIONS: [number, number][] = [
  [11, 12],           // shoulders
  [11, 13], [13, 15], // left arm
  [12, 14], [14, 16], // right arm
  [11, 23], [12, 24], // torso sides
  [23, 24],           // hips
  [23, 25], [25, 27], // left upper/lower leg
  [24, 26], [26, 28], // right upper/lower leg
  [27, 29], [29, 31], // left ankle/foot
  [28, 30], [30, 32], // right ankle/foot
  [0, 11],  [0, 12],  // head → shoulders
]

const BONE_COUNT = CONNECTIONS.length
const JOINT_COLOR_GOOD = new THREE.Color('#7AFF50')
const JOINT_COLOR_BAD  = new THREE.Color('#FF3232')
const COM_COLOR        = new THREE.Color('#7FC4FF')

// ── Inner scene — mutates Three.js objects directly, no React re-renders per frame

interface SceneProps {
  landmarks: [number, number, number][] | null
  isGood: boolean
  com: [number, number, number] | null
  target: [number, number, number]
}

function Scene({ landmarks, isGood, com, target }: SceneProps) {
  const jointsRef   = useRef<THREE.InstancedMesh>(null!)
  const jointMatRef = useRef<THREE.MeshBasicMaterial>(null!)
  const linesGeoRef = useRef<THREE.BufferGeometry>(null!)
  const linesMatRef = useRef<THREE.LineBasicMaterial>(null!)
  const comRef      = useRef<THREE.Mesh>(null!)
  const dummy       = useMemo(() => new THREE.Object3D(), [])

  // Initialise bone position buffer once on mount
  useEffect(() => {
    linesGeoRef.current.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(BONE_COUNT * 6), 3),
    )
  }, [])

  // Update skeleton geometry whenever the frame changes
  useEffect(() => {
    const color = isGood ? JOINT_COLOR_GOOD : JOINT_COLOR_BAD
    jointMatRef.current.color.copy(color)
    linesMatRef.current.color.copy(color)

    if (!landmarks) {
      for (let i = 0; i < 33; i++) {
        dummy.scale.setScalar(0)
        dummy.updateMatrix()
        jointsRef.current.setMatrixAt(i, dummy.matrix)
      }
      jointsRef.current.instanceMatrix.needsUpdate = true
      comRef.current.visible = false
      return
    }

    // Joints — one instanced mesh, one draw call
    for (let i = 0; i < 33; i++) {
      const [x, y, z] = landmarks[i] ?? [0, 0, 0]
      dummy.position.set(-x, -y, z) // flip Y (MP y-down→Three.js y-up), flip X (mirror)
      dummy.scale.setScalar(1)
      dummy.updateMatrix()
      jointsRef.current.setMatrixAt(i, dummy.matrix)
    }
    jointsRef.current.instanceMatrix.needsUpdate = true

    // Bones — update buffer attributes directly
    const attr = linesGeoRef.current.getAttribute('position') as THREE.BufferAttribute
    let vi = 0
    for (const [a, b] of CONNECTIONS) {
      const [ax, ay, az] = landmarks[a] ?? [0, 0, 0]
      const [bx, by, bz] = landmarks[b] ?? [0, 0, 0]
      attr.setXYZ(vi++, -ax, -ay, az)
      attr.setXYZ(vi++, -bx, -by, bz)
    }
    attr.needsUpdate = true

    // CoM
    if (com) {
      comRef.current.position.set(-com[0], -com[1], com[2])
      comRef.current.visible = true
    } else {
      comRef.current.visible = false
    }
  }, [landmarks, isGood, com, dummy])

  return (
    <>
      <color attach="background" args={['#0D1A2B']} />
      <ambientLight intensity={2} />

      <instancedMesh ref={jointsRef} args={[undefined, undefined, 33]} frustumCulled={false}>
        <sphereGeometry args={[0.018, 8, 8]} />
        <meshBasicMaterial ref={jointMatRef} color={JOINT_COLOR_GOOD} />
      </instancedMesh>

      <lineSegments frustumCulled={false}>
        <bufferGeometry ref={linesGeoRef} />
        <lineBasicMaterial ref={linesMatRef} color={JOINT_COLOR_GOOD} />
      </lineSegments>

      <mesh ref={comRef} visible={false} frustumCulled={false}>
        <sphereGeometry args={[0.06, 10, 10]} />
        <meshBasicMaterial color={COM_COLOR} />
      </mesh>

      <OrbitControls target={target} makeDefault />
    </>
  )
}

// ── Public component

interface Props {
  poseData: PoseEntry[]
  currentFrame: number
  isGood: boolean
}

export default function Skeleton3D({ poseData, currentFrame, isGood }: Props) {
  // Nearest pose entry for the current frame — O(n) but poseData never changes during playback
  const entry = useMemo(() => {
    if (!poseData.length) return null
    return poseData.reduce((best, e) =>
      Math.abs(e[0] - currentFrame) < Math.abs(best[0] - currentFrame) ? e : best,
    )
  }, [poseData, currentFrame])

  const landmarks = entry?.[1] ?? null
  const com       = entry?.[3] ?? null

  // Scene bounds computed once from all frames — used for initial camera + OrbitControls target
  const { cameraPos, target } = useMemo(() => {
    let minX = Infinity, maxX = -Infinity
    let minY = Infinity, maxY = -Infinity // Three.js Y (flipped from MediaPipe)
    let minZ = Infinity, maxZ = -Infinity

    for (const [, lms] of poseData) {
      if (!lms) continue
      for (const [x, y, z] of lms) {
        if (-x < minX) minX = -x; if (-x > maxX) maxX = -x
        if (-y < minY) minY = -y; if (-y > maxY) maxY = -y
        if (z  < minZ) minZ = z;  if (z  > maxZ) maxZ = z
      }
    }

    const cx   = (minX + maxX) / 2
    const cy   = (minY + maxY) / 2
    const cz   = (minZ + maxZ) / 2
    const span = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 0.5)
    const d    = span * 1.8

    return {
      target:    [cx, cy, cz] as [number, number, number],
      cameraPos: [cx + d * 0.6, cy + d * 0.35, cz + d] as [number, number, number],
    }
  }, [poseData])

  return (
    <Canvas
      camera={{ position: cameraPos, fov: 50, near: 0.01, far: 50 }}
      dpr={[1, 2]}
      style={{ width: '100%', height: '100%' }}
    >
      <Scene
        landmarks={landmarks}
        isGood={isGood}
        com={com}
        target={target}
      />
    </Canvas>
  )
}
