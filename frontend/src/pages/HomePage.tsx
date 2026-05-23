import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div className="max-w-4xl mx-auto space-y-0">

      {/* Hero */}
      <section className="text-center space-y-6 py-16">
        <h1 className="font-display text-7xl tracking-widest uppercase text-cream">
          Climb Smarter
        </h1>
        <p className="text-cream/70 text-lg max-w-xl mx-auto font-body leading-relaxed">
          CruxCam uses computer vision to analyze your climbing technique,
          frame by frame, in 3D.
        </p>
      </section>

      <div className="border-t border-cream/10" />

      {/* What you can do */}
      <section className="py-12 space-y-8">
        <p className="font-display tracking-widest uppercase text-cream text-2xl">What you can do</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card p-8 space-y-4 flex flex-col">
            <h2 className="font-display tracking-widest uppercase text-terracotta text-xl">Analyze</h2>
            <p className="text-cream/70 text-sm leading-relaxed flex-1">
              Upload a single climbing clip and get a full frame-by-frame breakdown. Set your arm
              angle threshold, trim the section you care about, and review your efficiency score
              alongside an annotated video and an interactive 3D skeleton you can scrub and rotate.
            </p>
            <Link to="/analyze" className="btn-primary self-start text-sm px-6 py-2">Go to Analyze</Link>
          </div>
          <div className="card p-8 space-y-4 flex flex-col">
            <h2 className="font-display tracking-widest uppercase text-terracotta text-xl">Compare</h2>
            <p className="text-cream/70 text-sm leading-relaxed flex-1">
              Load two clips side by side and process them in parallel. Both videos and 3D
              skeletons play in sync so you can spot differences in arm position, body tension,
              and efficiency across climbs, sessions, or techniques.
            </p>
            <Link to="/compare" className="btn-primary self-start text-sm px-6 py-2">Go to Compare</Link>
          </div>
        </div>
      </section>

      <div className="border-t border-cream/10" />

      {/* How it works */}
      <section className="py-12 space-y-8">
        <p className="font-display tracking-widest uppercase text-cream text-2xl">How it works</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            {
              title: 'Pose Detection',
              body: 'MediaPipe tracks 33 body landmarks per frame in 3D world space, giving angle, depth, and position data across your entire climb.',
            },
            {
              title: 'Efficiency Score',
              body: 'Elbow angles are computed in metric 3D space and each frame is classified as open or compressed. The score is the percentage of frames with arms extended.',
            },
            {
              title: '3D Skeleton Viewer',
              body: 'Scrub through your climb with a frame-synced, rotatable Three.js skeleton alongside the annotated video output.',
            },
          ].map(({ title, body }) => (
            <div key={title} className="space-y-3">
              <h3 className="font-display tracking-widest uppercase text-cream text-base">{title}</h3>
              <p className="text-cream/60 text-sm leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
        <p className="text-cream/50 text-sm leading-relaxed max-w-2xl">
          Center of mass is tracked across the full climb using biomechanically weighted segments
          and smoothed with an exponential moving average, visible as a moving dot in the
          annotated video output.
        </p>
      </section>

      <div className="border-t border-cream/10" />

      {/* About Me */}
      <section className="py-12 space-y-6">
        <p className="font-display tracking-widest uppercase text-cream text-2xl">About me</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
          <div className="space-y-4">
            <p className="text-cream/70 text-sm leading-relaxed">
              I am a climber who thinks in data. I hold a B.S. in Data Science from the University
              of Oregon, with minors in Computer Science and Mathematics, and I am currently
              pursuing a Master's in Computer Science at Georgia Tech.
            </p>
            <p className="text-cream/70 text-sm leading-relaxed">
              CruxCam came out of wanting to apply computer vision and machine learning to a
              problem I actually care about. Climbing gives you immediate physical feedback but
              very little structured data. This project is an attempt to close that gap.
            </p>
          </div>
          <div className="space-y-4">
            <p className="font-display tracking-widest uppercase text-cream text-2xl">Stack</p>
            <div className="flex flex-wrap gap-2">
              {[
                'MediaPipe', 'OpenCV', 'FastAPI', 'Celery', 'Redis',
                'React', 'Three.js', 'React Router', 'Vite', 'Tailwind CSS',
                'Docker', 'Railway', 'Vercel',
              ].map(tag => (
                <span
                  key={tag}
                  className="border border-cream/20 text-cream/50 text-xs font-body px-3 py-1 tracking-wide"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

    </div>
  )
}
