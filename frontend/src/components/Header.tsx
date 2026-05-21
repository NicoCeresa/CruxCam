export default function Header() {
  return (
    <header className="border-b border-navy-lighter px-6 py-4 flex items-center gap-3">
      {/* Carabiner-inspired logomark */}
      <svg viewBox="0 0 32 32" className="w-7 h-7 text-terracotta" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
        <ellipse cx="16" cy="16" rx="11" ry="6" transform="rotate(-35 16 16)" />
        <line x1="9" y1="11" x2="23" y2="21" />
      </svg>
      <span className="font-display text-xl font-700 tracking-widest uppercase text-cream">
        CruxCam
      </span>
      <span className="ml-auto text-cream/30 text-xs font-body tracking-wider uppercase">
        Climbing Analysis
      </span>
    </header>
  )
}
