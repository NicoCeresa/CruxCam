interface Props {
  onHome: () => void
}

export default function Header({ onHome }: Props) {
  return (
    <header className="bg-white border-b border-terracotta/20 px-6 py-4 flex items-center gap-3">
      <button onClick={onHome} className="flex items-center gap-3 hover:opacity-80 transition-opacity">
        <img src="/climbing_logo.png" alt="CruxCam" className="w-16 h-16 object-contain rounded" />
        <span className="font-display text-5xl font-700 tracking-widest uppercase text-terracotta">
          Crux Cam
        </span>
      </button>
      <span className="ml-auto text-terracotta/50 text-xs font-body tracking-wider uppercase">
        Climbing Analysis
      </span>
    </header>
  )
}
