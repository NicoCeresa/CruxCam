import { NavLink } from 'react-router-dom'

export default function Header() {
  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `font-body font-medium text-sm px-3 py-2 border-b-2 transition-colors duration-150 ${
      isActive
        ? 'border-terracotta text-cream'
        : 'border-transparent text-muted hover:text-cream'
    }`

  return (
    <header className="bg-navy border-b border-navy-lighter px-6 py-3 flex items-center gap-3">
      <NavLink to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
        <img src="/climbing_logo.png" alt="" className="w-10 h-10 object-cover rounded-full" />
        <span className="font-display text-3xl font-bold tracking-wider uppercase text-terracotta">
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
