import React, { lazy, Suspense } from 'react'
import { MotionPreference } from './MotionPreference'
const DemoPanel = import.meta.env.MODE === 'demo' ? lazy(() => import('./DemoPanel')) : null
import { createRoot } from 'react-dom/client'
import { Theme } from '@radix-ui/themes'
import '@radix-ui/themes/styles.css'
import './styles.css'
import './premium.css'
import App from './App'
import Admin from './Admin'
import './variant.css'

createRoot(document.getElementById('root')!).render(<React.StrictMode><MotionPreference><Theme appearance="dark" accentColor="purple">{location.pathname === '/admin' || location.pathname.startsWith('/admin/') ? <Admin /> : <App />}{DemoPanel && <Suspense><DemoPanel /></Suspense>}</Theme></MotionPreference></React.StrictMode>)
