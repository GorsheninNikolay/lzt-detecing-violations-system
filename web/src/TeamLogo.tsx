import './TeamLogo.css'

export default function TeamLogo({ size = 40, className = '' }: { size?: number; className?: string }) {
  return <span className={`team-logo ${className}`} style={{ width: size, height: size }} aria-hidden="true">
    <img src="/team-logo.png" alt="" />
    <img className="team-logo-caption" src="/team-logo.png" alt="" />
  </span>
}
