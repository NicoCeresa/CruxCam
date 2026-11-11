import { STATUS_TEXT, type Status } from '../utils/metrics'

interface Props {
  label: string
  value: string
  status: Status
}

export default function StatTile({ label, value, status }: Props) {
  return (
    <div className="px-2">
      <div className="label mb-1">{label}</div>
      <div className={`font-display text-2xl tabular-nums ${STATUS_TEXT[status]}`}>{value}</div>
    </div>
  )
}
