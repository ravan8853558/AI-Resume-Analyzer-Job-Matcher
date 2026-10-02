import './globals.css'
import type { Metadata } from 'next'
export const metadata: Metadata = { title: 'AI Resume Analyzer & Job Matcher', description: 'Analyze resumes and match them with jobs using AI.' }
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html> }
