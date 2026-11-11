import { TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

export default function Alert({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="rounded-md border border-warning/40 bg-warning/10 px-4 py-3 text-warning text-sm font-body flex items-start gap-2"
    >
      <TriangleAlert size={16} className="flex-shrink-0 mt-0.5" aria-hidden />
      <span>{children}</span>
    </div>
  )
}
