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

// [frame_num, world_lms (33x3) | null, is_good, com_xyz | null]
export type PoseEntry = [
  number,
  [number, number, number][] | null,
  boolean,
  [number, number, number] | null,
]

export interface AnalysisResult {
  good_frames: number
  bad_frames: number
  efficiency: number
  processed_video_path: string
  pose_data_3d: PoseEntry[] | null
}
