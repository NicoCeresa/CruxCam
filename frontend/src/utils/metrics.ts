// Status colours and thresholds shared by ResultsPanel, CompareColumn and Skeleton3D.
// Hex values mirror the `success` / `warning` / `danger` tokens in tailwind.config.js.

export type Status = 'success' | 'warning' | 'danger' | 'none'

export const STATUS_HEX: Record<Exclude<Status, 'none'>, string> = {
  success: '#86EFAC',
  warning: '#FACC15',
  danger:  '#FCA5A5',
}

export const STATUS_TEXT: Record<Status, string> = {
  success: 'text-success',
  warning: 'text-warning',
  danger:  'text-danger',
  none:    'text-muted',
}

export function angleStatus(deg: number | null | undefined): Status {
  if (deg == null) return 'none'
  if (deg > 90) return 'success'
  if (deg > 60) return 'warning'
  return 'danger'
}

// Hip-to-wall distance, normalized by torso length
export function hipStatus(dist: number | null | undefined): Status {
  if (dist == null) return 'none'
  if (dist < 0.7)  return 'success'
  if (dist < 1.1)  return 'warning'
  return 'danger'
}

export function gradeLabel(efficiency: number): { label: string; status: keyof typeof STATUS_HEX } {
  if (efficiency >= 70) return { label: 'Solid form', status: 'success' }
  if (efficiency >= 50) return { label: 'Needs work', status: 'warning' }
  return                       { label: 'Gripped',    status: 'danger'  }
}
