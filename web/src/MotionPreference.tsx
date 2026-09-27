import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { MotionConfig, useReducedMotion } from 'motion/react'
const Preference = createContext({ enabled: true, toggle: () => {} })
export function MotionPreference({ children }: { children: ReactNode }) {
  const [allowed, setAllowed] = useState(() => { try { return localStorage.getItem('analysis-motion') !== 'off' } catch { return false } })
  const reduced = useReducedMotion()
  const enabled = allowed && !reduced
  useEffect(() => { document.documentElement.dataset.motion = enabled ? 'on' : 'off'; document.documentElement.dataset.analysisMotion = enabled ? 'on' : 'off' }, [enabled])
  function toggle() { setAllowed(value => { try { localStorage.setItem('analysis-motion', value ? 'off' : 'on') } catch {} return !value }) }
  return <Preference.Provider value={{ enabled, toggle }}><MotionConfig reducedMotion={enabled ? 'user' : 'always'}>{children}</MotionConfig></Preference.Provider>
}
export const useMotionPreference = () => useContext(Preference)
export function MotionToggle() { const { enabled, toggle } = useMotionPreference(); return <button className="motion-toggle secondary" type="button" aria-pressed={enabled} onClick={toggle}>Движение: {enabled ? 'включено' : 'выключено'}</button> }
