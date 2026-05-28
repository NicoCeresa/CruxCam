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
const PLANE_GREEN      = new THREE.Color('#7AFF50')
const PLANE_YELLOW     = new THREE.Color('#FACC15')
const PLANE_RED        = new THREE.Color('#FF3232')

function planeColor(dist: number | null): THREE.Color {
  if (dist == null) return PLANE_GREEN
  if (dist < 0.7)  return PLANE_GREEN
  if (dist < 1.1)  return PLANE_YELLOW
  return PLANE_RED
}

// ── Inner scene — mutates Three.js objects directly, no React re-renders per frame

interface SceneProps {
  landmarks:     [number, number, number][] | null
  isGood:        boolean
  com:           [number, number, number] | null
  target:        [number, number, number]
  planeCentroid: [number, number, number] | null
  planeNormal:   [number, number, number] | null
  hipPlaneDist:  number | null
}

const _defaultNormal = new THREE.Vector3(0, 0, 1)
const _q = new THREE.Quaternion()
const _v = new THREE.Vector3()

function Scene({ landmarks, isGood, com, target, planeCentroid, planeNormal, hipPlaneDist }: SceneProps) {
  const jointsRef    = useRef<THREE.InstancedMesh>(null!)
  const jointMatRef  = useRef<THREE.MeshBasicMaterial>(null!)
  const linesGeoRef  = useRef<THREE.BufferGeometry>(null!)
  const linesMatRef  = useRef<THREE.LineBasicMaterial>(null!)
  const comRef       = useRef<THREE.Mesh>(null!)
  const planeRef     = useRef<THREE.Mesh>(null!)
  const planeMatRef  = useRef<THREE.MeshBasicMaterial>(null!)
  const hipLineRef   = useRef<THREE.LineSegments>(null!)
  const hipLineGeoRef = useRef<THREE.BufferGeometry>(null!)
  const dummy        = useMemo(() => new THREE.Object3D(), [])

  useEffect(() => {
    linesGeoRef.current.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(BONE_COUNT * 6), 3),
    )
    hipLineGeoRef.current.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(6), 3),
    )
  }, [])

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
      planeRef.current.visible = false
      hipLineRef.current.visible = false
      return
    }

    // Joints
    for (let i = 0; i < 33; i++) {
      const [x, y, z] = landmarks[i] ?? [0, 0, 0]
      dummy.position.set(-x, -y, z)
      dummy.scale.setScalar(1)
      dummy.updateMatrix()
      jointsRef.current.setMatrixAt(i, dummy.matrix)
    }
    jointsRef.current.instanceMatrix.needsUpdate = true

    // Bones
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

    // Contact plane
    if (planeCentroid && planeNormal) {
      const col = planeColor(hipPlaneDist)
      planeMatRef.current.color.copy(col)

      // Position — apply the same coordinate flip as landmarks
      planeRef.current.position.set(-planeCentroid[0], -planeCentroid[1], planeCentroid[2])

      _v.set(-planeNormal[0], -planeNormal[1], planeNormal[2]).normalize()
      _q.setFromUnitVectors(_defaultNormal, _v)
      planeRef.current.quaternion.copy(_q)
      planeRef.current.visible = true

      // Hip midpoint (landmarks 23 + 24)
      const [hLx, hLy, hLz] = landmarks[23] ?? [0, 0, 0]
      const [hRx, hRy, hRz] = landmarks[24] ?? [0, 0, 0]
      const hipX = (-hLx + -hRx) / 2
      const hipY = (-hLy + -hRy) / 2
      const hipZ = (hLz  + hRz ) / 2

      // Project hip onto plane
      const cX = -planeCentroid[0], cY = -planeCentroid[1], cZ = planeCentroid[2]
      const nX = _v.x, nY = _v.y, nZ = _v.z
      const d  = (hipX - cX) * nX + (hipY - cY) * nY + (hipZ - cZ) * nZ
      const pX = hipX - d * nX
      const pY = hipY - d * nY
      const pZ = hipZ - d * nZ

      const lineAttr = hipLineGeoRef.current.getAttribute('position') as THREE.BufferAttribute
      lineAttr.setXYZ(0, hipX, hipY, hipZ)
      lineAttr.setXYZ(1, pX, pY, pZ)
      lineAttr.needsUpdate = true
      hipLineRef.current.visible = true
    } else {
      planeRef.current.visible = false
      hipLineRef.current.visible = false
    }
  }, [landmarks, isGood, com, planeCentroid, planeNormal, hipPlaneDist, dummy])

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

      {/* Contact plane — semi-transparent, colored by hip distance */}
      <mesh ref={planeRef} visible={false} frustumCulled={false}>
        <circleGeometry args={[0.8, 48]} />
        <meshBasicMaterial ref={planeMatRef} color={PLANE_GREEN} transparent opacity={0.18} side={THREE.DoubleSide} />
      </mesh>

      {/* Hip-to-plane projection line */}
      <lineSegments ref={hipLineRef} visible={false} frustumCulled={false}>
        <bufferGeometry ref={hipLineGeoRef} />
        <lineBasicMaterial color="#FFFFFF" opacity={0.5} transparent />
      </lineSegments>

      <OrbitControls target={target} makeDefault />
    </>
  )
}

// ── Public component

interface Props {
  poseData:     PoseEntry[]
  currentFrame: number
  isGood:       boolean
}

export default function Skeleton3D({ poseData, currentFrame, isGood }: Props) {
  const entry = useMemo(() => {
    if (!poseData.length) return null
    return poseData.reduce((best, e) =>
      Math.abs(e[0] - currentFrame) < Math.abs(best[0] - currentFrame) ? e : best,
    )
  }, [poseData, currentFrame])

  const landmarks    = entry?.[1] ?? null
  const com          = entry?.[3] ?? null
  const hipPlaneDist = entry?.[6] ?? null
  const planeCentroid = entry?.[7] ?? null
  const planeNormal   = entry?.[8] ?? null

  const { cameraPos, target } = useMemo(() => {
    let minX = Infinity, maxX = -Infinity
    let minY = Infinity, maxY = -Infinity
    let minZ = Infinity, maxZ = -Infinity
    let nx = 0, ny = 0, nz = 0, nCount = 0

    for (const entry of poseData) {
      const lms = entry[1]
      if (lms) {
        for (const [x, y, z] of lms) {
          if (-x < minX) minX = -x; if (-x > maxX) maxX = -x
          if (-y < minY) minY = -y; if (-y > maxY) maxY = -y
          if (z  < minZ) minZ = z;  if (z  > maxZ) maxZ = z
        }
      }
      const n = entry[8]
      if (n) { nx += n[0]; ny += n[1]; nz += n[2]; nCount++ }
    }

    const cx   = (minX + maxX) / 2
    const cy   = (minY + maxY) / 2
    const cz   = (minZ + maxZ) / 2
    const span = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 0.5)
    const d    = span * 1.8

    // Use the averaged contact-plane normal for camera position and as the fixed
    // wall orientation — computed once so the plane doesn't spin during playback.
    let cameraPos: [number, number, number]
    let wallNormal: [number, number, number] | null = null
    if (nCount > 0) {
      const len = Math.sqrt(nx * nx + ny * ny + nz * nz)
      wallNormal = [nx / len, ny / len, nz / len]
      cameraPos = [cx + (-wallNormal[0]) * d, cy + (-wallNormal[1]) * d, cz + wallNormal[2] * d]
    } else {
      cameraPos = [cx, cy + d * 0.3, cz + d]
    }

    return {
      target:    [cx, cy, cz] as [number, number, number],
      cameraPos,
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
        planeCentroid={planeCentroid}
        planeNormal={planeNormal}
        hipPlaneDist={hipPlaneDist}
      />
    </Canvas>
  )
}
