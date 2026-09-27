import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { MotionConfig } from 'motion/react'
const Preference = createContext({ enabled: true, systemReduced: false, toggle: () => {} })
export function MotionPreference({ children }: { children: ReactNode }) {
  const [allowed, setAllowed] = useState(() => { try { return localStorage.getItem('analysis-motion') !== 'off' } catch { return false } })
  const [reduced, setReduced] = useState(() => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => { if (typeof matchMedia !== 'function') return; const query = matchMedia('(prefers-reduced-motion: reduce)'); const update = () => setReduced(query.matches); update(); query.addEventListener?.('change', update); return () => query.removeEventListener?.('change', update) }, [])
  const enabled = allowed && !reduced
  useEffect(() => { document.documentElement.dataset.motion = enabled ? 'on' : 'off'; document.documentElement.dataset.analysisMotion = enabled ? 'on' : 'off' }, [enabled])
  function toggle() { if (reduced) return; setAllowed(value => { try { localStorage.setItem('analysis-motion', value ? 'off' : 'on') } catch {} return !value }) }
  return <Preference.Provider value={{ enabled, systemReduced: reduced, toggle }}><MotionConfig reducedMotion={enabled ? 'user' : 'always'}>{children}</MotionConfig></Preference.Provider>
}
export const useMotionPreference = () => useContext(Preference)
export function MotionToggle() { const { enabled, systemReduced, toggle } = useMotionPreference(); return <button className="motion-toggle secondary" type="button" aria-pressed={enabled} disabled={systemReduced} title={systemReduced ? 'Движение отключено настройками системы. Сохранённый выбор применится после снятия ограничения.' : undefined} onClick={toggle}>Движение: {systemReduced ? 'выключено системой' : enabled ? 'включено' : 'выключено'}</button> }
