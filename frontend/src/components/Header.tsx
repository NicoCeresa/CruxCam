import { NavLink } from 'react-router-dom'

export default function Header() {
  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `font-display tracking-widest uppercase text-sm px-4 py-2 border-b-2 transition-colors duration-150 ${
      isActive
        ? 'border-terracotta text-terracotta'
        : 'border-transparent text-navy/80 hover:text-navy'
    }`

  return (
    <header className="bg-white border-b border-terracotta/20 px-6 py-4 flex items-center gap-3">
      <NavLink to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
        <img src="/climbing_logo.png" alt="CruxCam" className="w-16 h-16 object-contain rounded" />
        <span className="font-display text-5xl font-700 tracking-widest uppercase text-terracotta">
          Crux Cam
        </span>
      </NavLink>
      <nav className="ml-auto flex items-center gap-1">
        <NavLink to="/" end className={tabClass}>Home</NavLink>
        <NavLink to="/analyze" className={tabClass}>Analyze</NavLink>
        <NavLink to="/compare" className={tabClass}>Compare</NavLink>
      </nav>
    </header>
  )
}
