export default function Header() {
  return (
    <header className="border-b border-navy-lighter px-6 py-4 flex items-center gap-3">
      <img src="/climbing_logo.png" alt="CruxCam" className="w-8 h-8 object-contain rounded" />
      <span className="font-display text-xl font-700 tracking-widest uppercase text-cream">
        CruxCam
      </span>
      <span className="ml-auto text-cream/30 text-xs font-body tracking-wider uppercase">
        Climbing Analysis
      </span>
    </header>
  )
}
