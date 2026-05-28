export interface VideoInfo {
  fps: number
  width: number
  height: number
  total_frames: number
  duration: number
  preview_id: string
}

export interface JobStatus {
  status: 'pending' | 'processing' | 'complete' | 'failed'
  progress: number
  error?: string
}

export type PoseEntry = [
  number,                              // 0: frame_num
  [number, number, number][] | null,   // 1: world_lms (33×3)
  boolean,                             // 2: is_good
  [number, number, number] | null,     // 3: com_xyz
  number | null,                       // 4: r_angle (degrees)
  number | null,                       // 5: l_angle (degrees)
  number | null,                       // 6: hip_plane_dist (normalized by torso length)
  [number, number, number] | null,     // 7: plane_centroid (smoothed contact-point centroid)
  [number, number, number] | null,     // 8: plane_normal   (smoothed unit normal)
]

export interface AnalysisResult {
  good_frames: number
  bad_frames: number
  efficiency: number
  processed_video_path: string
  pose_data_3d: PoseEntry[] | null
}
