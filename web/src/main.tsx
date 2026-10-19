import React from 'react'
import { MotionPreference } from './MotionPreference'
import { createRoot } from 'react-dom/client'
import AccountShell from './AccountShell'
import { Theme } from '@radix-ui/themes'
import '@radix-ui/themes/styles.css'
import './styles.css'
import './premium.css'
import App from './App'
import Admin from './Admin'
import './variant.css'
import './Header.css'

createRoot(document.getElementById('root')!).render(<React.StrictMode><MotionPreference>{location.pathname === '/admin' || location.pathname.startsWith('/admin/') ? <Theme appearance="dark" accentColor="purple"><Admin /></Theme> : <AccountShell><App /></AccountShell>}</MotionPreference></React.StrictMode>)
