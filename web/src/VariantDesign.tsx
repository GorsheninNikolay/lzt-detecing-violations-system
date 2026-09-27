import { useEffect, useRef, useState } from 'react'
import { motion, useScroll, useTransform } from 'motion/react'
import { useMotionPreference } from './MotionPreference'
function useFinePointer() {
  const [fine, setFine] = useState(false)
  useEffect(() => { if (typeof matchMedia === 'undefined') return; const query = matchMedia('(pointer: fine) and (min-width: 900px)'); const update = () => setFine(query.matches); update(); query.addEventListener?.('change', update); return () => query.removeEventListener?.('change', update) }, [])
  return fine
}
function useVisible(ref: React.RefObject<HTMLDivElement | null>) {
  const [visible, setVisible] = useState(false)
  useEffect(() => { if (!ref.current || typeof IntersectionObserver === 'undefined') return; const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting)); observer.observe(ref.current); return () => observer.disconnect() }, [ref])
  return visible
}
function Architecture({ alternate = false }: { alternate?: boolean }) {
  return <svg viewBox="0 0 640 300" fill="none" aria-hidden="true"><path d="M0 250L340 295L640 180M180 238V65L290 25L470 67V238L360 280L180 238Z" fill={alternate ? '#6c547b' : '#805572'} stroke="#d9b5d6" strokeWidth="2"/><path d="M180 65L360 107L470 67M360 107V280M215 90V218M250 98V226M285 108V237M320 118V245M380 124L450 98M380 154L450 128M380 184L450 158M380 214L450 188M380 244L450 218" stroke="#f2d7ed" strokeWidth="2"/><path d="M42 200V55H145M40 78H120M63 55V190M80 55V187M102 55V175" stroke="#c9a7c4" strokeWidth="2"/><path d="M30 210L155 238M486 237L608 190" stroke="#6b506c" strokeWidth="2"/></svg>
}
export function ProjectCover({ name }: { name: string }) {
  const { enabled } = useMotionPreference(); const fine = useFinePointer()
  const [tilt, setTilt] = useState({ rotateX: 0, rotateY: 0 })
  return <motion.div className="project-cover dimensional-cover" aria-hidden="true" initial={false} animate={enabled && fine ? tilt : { rotateX: 0, rotateY: 0 }} transition={{ type: 'spring', stiffness: 170, damping: 24 }} onPointerMove={event => { if (!enabled || !fine || event.pointerType === 'touch') return; const rect = event.currentTarget.getBoundingClientRect(); setTilt({ rotateX: (event.clientY - rect.top - rect.height / 2) / rect.height * -8, rotateY: (event.clientX - rect.left - rect.width / 2) / rect.width * 10 }) }} onPointerLeave={() => setTilt({ rotateX: 0, rotateY: 0 })}><Architecture alternate={name.includes('Северный')} /></motion.div>
}
// Adapted from Aceternity ThreeDMarquee; only decorative architectural covers move.
export function EntryScene() {
  const ref = useRef<HTMLDivElement>(null); const inView = useVisible(ref); const { enabled } = useMotionPreference(); const fine = useFinePointer()
  const moving = enabled && fine && inView
  return <div className="marquee-scene" aria-hidden="true" ref={ref} data-moving={moving}><div className="marquee-plane">{Array.from({ length: 4 }, (_, column) => <motion.div className="marquee-column" key={column} initial={false} animate={{ y: moving ? (column % 2 ? -32 : 32) : 0 }} transition={moving ? { duration: column % 2 ? 12 : 15, repeat: Infinity, repeatType: 'reverse', ease: 'easeInOut' } : { duration: 0 }}>{[0, 1, 2].map(row => <div key={row}><Architecture alternate={(column + row) % 2 === 1} /></div>)}</motion.div>)}</div></div>
}
// Adapted from Aceternity ContainerScroll; working images never enter this container.
export function OverviewScene() {
  const ref = useRef<HTMLDivElement>(null); const inView = useVisible(ref); const { enabled } = useMotionPreference(); const fine = useFinePointer()
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })
  const rotate = useTransform(scrollYProgress, [0, .6], [14, 0]); const scale = useTransform(scrollYProgress, [0, .6], [.94, 1])
  return <div className="overview-presentation" ref={ref} aria-hidden="true"><motion.div style={{ rotateX: enabled && fine && inView ? rotate : 0, scale: enabled && fine && inView ? scale : 1 }}><Architecture /><p>От фотографии<br />к обоснованному решению</p></motion.div></div>
}
