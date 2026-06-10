export function GlassCard({ eyebrow, title, subtitle, children, className = '' }) {
  return (
    <section className={`glass-panel rounded-[1.5rem] p-5 ${className}`}>
      {eyebrow ? <p className="card-title">{eyebrow}</p> : null}
      {title ? <h2 className="card-heading">{title}</h2> : null}
      {subtitle ? <p className="mt-2 max-w-2xl text-sm leading-6 text-white/65">{subtitle}</p> : null}
      <div className="mt-5">{children}</div>
    </section>
  )
}
