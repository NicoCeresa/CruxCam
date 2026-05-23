import { useNavigate } from 'react-router-dom'
import { Link } from 'react-router-dom'

export default function HomePage() {
  const navigate = useNavigate()

  return (
    <div className="space-y-20">

      {/* Hero */}
      <section className="text-center space-y-6 pt-8">
        <h1 className="font-display text-7xl tracking-widest uppercase text-cream">
          Climb Smarter
        </h1>
        <p className="text-cream/70 text-lg max-w-xl mx-auto font-body leading-relaxed">
          CruxCam uses computer vision to analyze your climbing technique —
          frame by frame, in 3D.
        </p>
        <button onClick={() => navigate('/analyze')} className="btn-primary">
          Analyze Your Footage
        </button>
      </section>

      {/* Tabs overview */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card p-8 space-y-4 flex flex-col">
          <h2 className="font-display tracking-widest uppercase text-terracotta text-2xl">Analyze</h2>
          <p className="text-cream/70 text-sm leading-relaxed flex-1">
            Upload a single climbing clip and get a full frame-by-frame breakdown. Set your arm
            angle threshold, trim the section you care about, and see your efficiency score
            alongside an annotated video and an interactive 3D skeleton viewer you can scrub and
            rotate freely.
          </p>
          <Link to="/analyze" className="btn-primary self-start text-sm px-6 py-2">
            Go to Analyze
          </Link>
        </div>
        <div className="card p-8 space-y-4 flex flex-col">
          <h2 className="font-display tracking-widest uppercase text-terracotta text-2xl">Compare</h2>
          <p className="text-cream/70 text-sm leading-relaxed flex-1">
            Load two clips side by side and analyze them in parallel. Both videos and skeletons
            play in sync so you can spot differences in arm position, body tension, and efficiency
            across climbs, sessions, or techniques.
          </p>
          <Link to="/compare" className="btn-primary self-start text-sm px-6 py-2">
            Go to Compare
          </Link>
        </div>
      </section>

      {/* About CruxCam */}
      <section className="space-y-6">
        <h2 className="font-display tracking-widest uppercase text-cream text-2xl">About CruxCam</h2>
        <p className="text-cream/70 text-sm leading-relaxed max-w-3xl">
          CruxCam started from a simple observation: climbers spend hours on the wall but have very
          little objective data about what they are actually doing. Video exists, but watching it back
          gives you impressions, not numbers. CruxCam turns that footage into structured feedback.
        </p>
        <p className="text-cream/70 text-sm leading-relaxed max-w-3xl">
          On every frame of your climb, MediaPipe detects 33 body landmarks in 3D world space,
          calibrated in meters relative to the hips. Elbow angles are computed at both joints using
          vector math in that metric space, and each frame is classified based on whether your arms
          are extended or compressed. The output is a single efficiency score: the percentage of
          frames where your skeleton is bearing load the way it should be.
        </p>
        <p className="text-cream/70 text-sm leading-relaxed max-w-3xl">
          Alongside the score, CruxCam tracks your center of mass across the full climb using
          biomechanically weighted body segments, smoothed with an exponential moving average. You
          can watch this in the annotated video output and explore the full pose data in a
          frame-synced, rotatable 3D skeleton viewer built with Three.js.
        </p>
        <p className="text-cream/70 text-sm leading-relaxed max-w-3xl">
          The goal is to give climbers the kind of feedback that used to require a coach standing
          next to the wall. Upload a clip, set your angle threshold, trim the section you care about,
          and get a breakdown in under a minute.
        </p>
      </section>

      {/* Features */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          {
            title: 'Pose Detection',
            body: 'MediaPipe tracks 33 body landmarks per frame in 3D world space, giving angle, depth, and position data across every frame of your climb.',
          },
          {
            title: 'Efficiency Score',
            body: 'Every frame is classified based on arm extension. The final score is the percentage of frames where your arms are out and your skeleton is bearing load correctly.',
          },
          {
            title: '3D Skeleton Viewer',
            body: 'Scrub through your climb with a frame-synced, rotatable Three.js skeleton alongside the annotated video.',
          },
        ].map(({ title, body }) => (
          <div key={title} className="card p-6 space-y-3">
            <h3 className="font-display tracking-widest uppercase text-terracotta text-lg">{title}</h3>
            <p className="text-cream/70 text-sm leading-relaxed">{body}</p>
          </div>
        ))}
      </section>

      {/* Stack */}
      <section className="space-y-4">
        <h2 className="font-display tracking-widest uppercase text-cream text-2xl">Stack</h2>
        <div className="flex flex-wrap gap-2">
          {[
            'MediaPipe', 'OpenCV', 'FastAPI', 'Celery', 'Redis',
            'React', 'Three.js', 'React Router', 'Vite', 'Tailwind CSS',
            'Docker', 'Railway', 'Vercel',
          ].map(tag => (
            <span
              key={tag}
              className="border border-cream/20 text-cream/60 text-xs font-body px-3 py-1 tracking-wide"
            >
              {tag}
            </span>
          ))}
        </div>
      </section>

      {/* About */}
      <section className="card p-8 space-y-4">
        <h2 className="font-display tracking-widest uppercase text-cream text-2xl">About Me</h2>
        <p className="text-cream/70 text-sm leading-relaxed max-w-2xl">
          I am a climber who thinks in data. I hold a B.S. in Data Science from the University of
          Oregon, with minors in Computer Science and Mathematics, and I am currently pursuing a
          Master's in Computer Science at Georgia Tech.
        </p>
        <p className="text-cream/70 text-sm leading-relaxed max-w-2xl">
          CruxCam came out of wanting to apply computer vision and machine learning to a problem I
          actually care about. Climbing gives you immediate physical feedback but very little
          structured data. This project is an attempt to close that gap, and a platform to keep
          building on as my skills in the ML engineering space grow.
        </p>
      </section>

    </div>
  )
}
